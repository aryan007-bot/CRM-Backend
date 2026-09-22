import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.core.logging import logger
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.creditor import Creditor
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.import_job import Import, ImportRow
from app.import_engine.mapper import suggest_column_mappings, validate_mapping
from app.import_engine.parser import parse_file_contents
from app.import_engine.validator import validate_import_rows
from app.schemas.import_job import (
    ConfirmImportResponse,
    UploadResponse,
    ValidateResponse,
    ValidateSummary,
    ValidationErrorItem,
)
from app.utils.pagination import paginate


class ImportService:
    @staticmethod
    def upload_file(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        filename: str,
        content: bytes,
    ) -> UploadResponse:
        file_type, detected_columns, raw_rows, total_rows = parse_file_contents(filename, content)

        import_job = Import(
            organization_id=organization_id,
            filename=filename,
            file_type=file_type,
            status="uploaded",
            total_rows=total_rows,
            valid_rows=0,
            invalid_rows=0,
            duplicate_rows=0,
            imported_rows=0,
            created_by=user_id,
        )
        db.add(import_job)
        db.flush()

        # Batch insert raw rows into ImportRow
        rows_to_insert = [
            ImportRow(
                import_id=import_job.id,
                row_number=idx,
                raw_data=row,
                status="pending",
            )
            for idx, row in enumerate(raw_rows, start=1)
        ]
        db.add_all(rows_to_insert)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPLOAD_IMPORT_FILE",
            entity_type="IMPORT",
            entity_id=import_job.id,
            metadata_json={"filename": filename, "total_rows": total_rows},
        )
        db.add(audit)
        db.commit()
        db.refresh(import_job)

        return UploadResponse(
            import_id=import_job.id,
            filename=filename,
            file_type=file_type,
            detected_columns=detected_columns,
            row_count=total_rows,
            suggested_mapping=suggest_column_mappings(detected_columns),
        )

    @staticmethod
    def get_import(db: Session, organization_id: uuid.UUID, import_id: uuid.UUID) -> Import:
        stmt = select(Import).where(
            Import.id == import_id,
            Import.organization_id == organization_id,
        )
        import_job = db.scalar(stmt)
        if not import_job:
            raise NotFoundException("Import job not found", code="IMPORT_NOT_FOUND")
        return import_job

    @staticmethod
    def get_import_detail(db: Session, organization_id: uuid.UUID, import_id: uuid.UUID) -> Import:
        """Loads an import job with the detected columns and mapping suggestions attached.

        These are derived from the stored raw rows so the mapping screen is
        reload-safe — it never depends on state returned by the upload call.
        """
        import_job = ImportService.get_import(db, organization_id, import_id)

        first_row = db.scalar(
            select(ImportRow)
            .where(ImportRow.import_id == import_job.id)
            .order_by(ImportRow.row_number.asc())
            .limit(1)
        )
        detected_columns = list(first_row.raw_data.keys()) if first_row and first_row.raw_data else []

        # Transient attributes consumed by ImportDetailOut.model_validate.
        import_job.detected_columns = detected_columns  # type: ignore[attr-defined]
        import_job.suggested_mapping = suggest_column_mappings(detected_columns)  # type: ignore[attr-defined]
        return import_job

    @staticmethod
    def validate_import(
        db: Session,
        organization_id: uuid.UUID,
        import_id: uuid.UUID,
        mapping: Dict[str, str],
    ) -> ValidateResponse:
        import_job = ImportService.get_import(db, organization_id, import_id)

        if import_job.status == "completed":
            raise ConflictException("Import has already been completed", code="IMPORT_ALREADY_COMPLETED")

        # Fetch all import rows for this job ordered by row_number
        stmt = select(ImportRow).where(ImportRow.import_id == import_job.id).order_by(ImportRow.row_number.asc())
        db_rows = list(db.scalars(stmt).all())

        raw_rows = [r.raw_data for r in db_rows]
        detected_columns = list(raw_rows[0].keys()) if raw_rows else []

        validate_mapping(mapping, detected_columns)

        summary_dict, errors_list, warnings_list, processed_rows = validate_import_rows(
            db=db,
            organization_id=organization_id,
            raw_rows=raw_rows,
            mapping=mapping,
        )

        # Update import job summary counts
        import_job.valid_rows = summary_dict["valid_rows"]
        import_job.invalid_rows = summary_dict["invalid_rows"]
        import_job.duplicate_rows = summary_dict["duplicate_rows"]
        import_job.status = "processing"

        # Update each row in the DB with normalized result and status
        preview_data: List[Dict[str, Any]] = []
        for db_row, proc_row in zip(db_rows, processed_rows):
            db_row.normalized_data = proc_row["normalized_data"]
            db_row.status = proc_row["status"]
            db_row.error_data = proc_row["error_data"]
            if proc_row["status"] == "valid" and len(preview_data) < 10:
                preview_data.append(proc_row["normalized_data"])

        db.commit()

        validation_errors = [
            ValidationErrorItem(
                row=err["row"],
                field=err["field"],
                code=err["code"],
                message=err["message"],
            )
            for err in errors_list
        ]

        return ValidateResponse(
            summary=ValidateSummary(
                total_rows=summary_dict["total_rows"],
                valid_rows=summary_dict["valid_rows"],
                invalid_rows=summary_dict["invalid_rows"],
                duplicate_rows=summary_dict["duplicate_rows"],
            ),
            warnings=warnings_list,
            errors=validation_errors,
            preview=preview_data,
        )

    @staticmethod
    def confirm_import(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        import_id: uuid.UUID,
    ) -> ConfirmImportResponse:
        import_job = ImportService.get_import(db, organization_id, import_id)

        # Idempotency check: Cannot confirm twice
        if import_job.status == "completed":
            raise ConflictException(
                "This import has already been confirmed and processed.",
                code="IMPORT_ALREADY_COMPLETED",
            )

        # Fetch only valid rows
        stmt = (
            select(ImportRow)
            .where(
                ImportRow.import_id == import_job.id,
                ImportRow.status == "valid",
            )
            .order_by(ImportRow.row_number.asc())
        )
        valid_rows = list(db.scalars(stmt).all())

        if not valid_rows:
            raise ValidationException(
                "No valid rows found to import. Please validate mappings and resolve errors first."
            )

        # Cache existing creditors for this organization to avoid duplicate inserts
        creditors_stmt = select(Creditor).where(Creditor.organization_id == organization_id)
        existing_creditors: Dict[str, Creditor] = {c.name.lower(): c for c in db.scalars(creditors_stmt).all()}

        imported_count = 0

        # Execute transactional creation. Confirmation is all-or-nothing: any
        # failure rolls the whole batch back so a partial import can never leave
        # orphaned customers, phones, creditors or accounts behind.
        try:
            for row in valid_rows:
                norm = row.normalized_data
                if not norm:
                    continue

                customer_name = norm["customer_name"]
                phone_raw = norm["phone"]
                phone_norm = norm["normalized_phone"]
                account_num = norm["account_number"]
                amount = Decimal(norm["outstanding_amount"])
                due_date = (
                    datetime.strptime(norm["due_date"], "%Y-%m-%d").date()
                    if norm.get("due_date")
                    else None
                )
                creditor_name = norm.get("creditor_name")
                email = norm.get("email")

                # 1. Resolve creditor
                creditor_id = None
                if creditor_name:
                    c_key = creditor_name.strip().lower()
                    if c_key in existing_creditors:
                        creditor_id = existing_creditors[c_key].id
                    else:
                        new_creditor = Creditor(
                            organization_id=organization_id,
                            name=creditor_name.strip(),
                            status="active",
                        )
                        db.add(new_creditor)
                        db.flush()
                        existing_creditors[c_key] = new_creditor
                        creditor_id = new_creditor.id

                # 2. Create customer and primary phone
                customer = Customer(
                    organization_id=organization_id,
                    name=customer_name,
                    email=email,
                    status="active",
                )
                db.add(customer)
                db.flush()

                customer_phone = CustomerPhone(
                    customer_id=customer.id,
                    phone=phone_raw,
                    normalized_phone=phone_norm,
                    phone_type="mobile",
                    is_primary=True,
                    is_verified=False,
                )
                db.add(customer_phone)

                # 3. Create Account
                account = Account(
                    organization_id=organization_id,
                    customer_id=customer.id,
                    creditor_id=creditor_id,
                    account_number=account_num,
                    outstanding_amount=amount,
                    currency="INR",
                    due_date=due_date,
                    status="active",
                )
                db.add(account)

                row.status = "imported"
                imported_count += 1

            import_job.imported_rows = imported_count
            import_job.status = "completed"

            audit = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="CONFIRM_IMPORT",
                entity_type="IMPORT",
                entity_id=import_job.id,
                metadata_json={"imported_rows": imported_count},
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(f"Import {import_id} failed and was rolled back")
            raise

        return ConfirmImportResponse(
            import_id=import_job.id,
            status=import_job.status,
            imported_rows=imported_count,
            total_rows=import_job.total_rows,
        )

    @staticmethod
    def list_imports(
        db: Session,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Import], int]:
        query = select(Import).where(Import.organization_id == organization_id)
        if status:
            query = query.where(Import.status == status)
        query = query.order_by(Import.created_at.desc())
        return paginate(db, query, page=page, page_size=page_size)
