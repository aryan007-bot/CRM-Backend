import io
import os
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.core.config import settings
from app.core.errors import PayloadTooLargeException, ValidationException


def parse_file_contents(
    filename: str,
    content: bytes,
) -> Tuple[str, List[str], List[Dict[str, Any]], int]:
    """Parses .csv or .xlsx file contents into detected columns, raw row records, and row count.
    Returns (file_type, detected_columns, raw_rows, total_rows).
    """
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise PayloadTooLargeException(
            f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB"
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationException(
            f"Unsupported file format '{ext}'. Only .xlsx and .csv are supported."
        )

    file_type = ext.lstrip(".")

    try:
        if file_type == "csv":
            # Read CSV with pandas, auto-detecting comma or tab delimiter
            df = pd.read_csv(
                io.BytesIO(content),
                dtype=str,
                keep_default_na=False,
                na_values=[""],
            )
        else:
            # Read Excel (.xlsx) using openpyxl engine
            df = pd.read_excel(
                io.BytesIO(content),
                engine="openpyxl",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
            )
    except Exception as e:
        raise ValidationException(f"Failed to parse {file_type.upper()} file: {str(e)}")

    df = df.fillna("")

    # Clean header columns: strip whitespace and stringify
    df.columns = [str(col).strip() for col in df.columns]
    detected_columns = [col for col in df.columns if col and not col.startswith("Unnamed:")]

    total_rows = len(df)
    if total_rows == 0:
        raise ValidationException("The uploaded file is empty (0 rows found).")

    if total_rows > settings.MAX_IMPORT_ROWS:
        raise ValidationException(
            f"File row count ({total_rows}) exceeds maximum allowed ({settings.MAX_IMPORT_ROWS})."
        )

    # Convert DataFrame rows into list of dictionaries
    raw_rows = df[detected_columns].to_dict(orient="records")

    return file_type, detected_columns, raw_rows, total_rows
