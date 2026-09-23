from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.telephony.asterisk import AsteriskTelephonyAdapter
from app.db.models.call import Call
from app.db.models.telephony import TelephonyGateway
from app.services.telephony_core.outbound_dial_service import OutboundDialService
from app.services.telephony_core.phone_number_service import PhoneNumberService


class TelephonyPreflightService:
    """Evaluates readiness of all telephony prerequisites before initiating a call."""

    @classmethod
    def run_preflight(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        recipient_phone: str,
        caller_phone: Optional[str],
        mode: str = "LIVE",
        asterisk_adapter: Optional[AsteriskTelephonyAdapter] = None,
    ) -> Dict[str, Any]:
        """Runs preflight validation checks.
        
        Returns:
            {
                "ready": bool,
                "mode": str,
                "normalized_phone": str,
                "resolved_caller_id": str,
                "checks": List[Dict[str, Any]],
                "error_code": Optional[str],
                "error_message": Optional[str],
            }
        """
        checks: List[Dict[str, Any]] = []
        is_ready = True
        primary_error_code = None
        primary_error_msg = None

        # 1. Phone number validation
        valid_phone, norm_phone, phone_err = PhoneNumberService.normalize_phone(recipient_phone)
        if not valid_phone:
            is_ready = False
            primary_error_code = primary_error_code or "INVALID_DESTINATION"
            primary_error_msg = primary_error_msg or phone_err
            checks.append({
                "name": "phone_number",
                "status": "FAIL",
                "code": "INVALID_DESTINATION",
                "message": phone_err,
            })
        else:
            checks.append({
                "name": "phone_number",
                "status": "PASS",
                "normalized": norm_phone,
            })

        # 2. Active Call Collision Protection
        existing_active = db.scalar(
            select(Call).where(
                Call.organization_id == organization_id,
                Call.customer_id == customer_id,
                Call.status.in_(["created", "connecting", "ringing", "connected", "ai_talking", "customer_talking"]),
            )
        )
        if existing_active:
            is_ready = False
            primary_error_code = primary_error_code or "ACTIVE_CALL_EXISTS"
            primary_error_msg = primary_error_msg or f"Customer already has an active call (ID: {existing_active.id})"
            checks.append({
                "name": "active_call_protection",
                "status": "FAIL",
                "code": "ACTIVE_CALL_EXISTS",
                "message": primary_error_msg,
            })
        else:
            checks.append({"name": "active_call_protection", "status": "PASS"})

        # 3. Caller ID Validation
        valid_cid, resolved_cid, cid_err = OutboundDialService.resolve_caller_id(caller_phone)
        if not valid_cid:
            is_ready = False
            primary_error_code = primary_error_code or "INVALID_CALLER_ID"
            primary_error_msg = primary_error_msg or cid_err
            checks.append({
                "name": "caller_id",
                "status": "FAIL",
                "code": "INVALID_CALLER_ID",
                "message": cid_err,
            })
        else:
            checks.append({"name": "caller_id", "status": "PASS", "resolved": resolved_cid})

        # 4. Calling Window Check
        now_hour = datetime.now(timezone.utc).hour
        # Default window: 09:00 - 19:00 IST (approx 03:30 - 13:30 UTC), bypassable in DEV/TEST
        calling_window_enforced = os.getenv("ENFORCE_CALLING_WINDOW", "false").lower() == "true"
        if calling_window_enforced and not (3 <= now_hour <= 14):
            is_ready = False
            primary_error_code = primary_error_code or "CALLING_WINDOW_VIOLATION"
            primary_error_msg = primary_error_msg or "Outbound calls restricted outside 09:00 - 19:00 local window"
            checks.append({
                "name": "calling_window",
                "status": "FAIL",
                "code": "CALLING_WINDOW_VIOLATION",
                "message": primary_error_msg,
            })
        else:
            checks.append({"name": "calling_window", "status": "PASS"})

        # In SIMULATION mode, hardware/trunk checks are bypassed
        if mode.upper() == "SIMULATION":
            checks.append({"name": "telephony_mode", "status": "PASS", "mode": "SIMULATION"})
            return {
                "ready": is_ready,
                "mode": "SIMULATION",
                "normalized_phone": norm_phone,
                "resolved_caller_id": resolved_cid,
                "checks": checks,
                "error_code": primary_error_code,
                "error_message": primary_error_msg,
            }

        # 5. LIVE MODE: Asterisk Reachability
        adapter = asterisk_adapter or AsteriskTelephonyAdapter()
        ast_up = adapter.is_reachable()
        if not ast_up:
            is_ready = False
            primary_error_code = primary_error_code or "ASTERISK_UNAVAILABLE"
            primary_error_msg = primary_error_msg or f"Asterisk ARI PBX is unreachable at {adapter.ari_url}"
            checks.append({
                "name": "asterisk",
                "status": "FAIL",
                "code": "ASTERISK_UNAVAILABLE",
                "message": primary_error_msg,
            })
        else:
            checks.append({"name": "asterisk", "status": "PASS", "endpoint": adapter.ari_url})

        # 6. LIVE MODE: Gateway / Trunk Registration
        gateway = db.scalar(
            select(TelephonyGateway).where(
                TelephonyGateway.organization_id == organization_id,
                TelephonyGateway.status == "ONLINE",
            )
        )
        if not gateway:
            # Check if SIP trunk fallback is explicitly configured in env
            sip_trunk_configured = bool(os.getenv("SIP_TRUNK_HOST") or os.getenv("OUTBOUND_TRUNK"))
            if not sip_trunk_configured:
                is_ready = False
                primary_error_code = primary_error_code or "GSM_GATEWAY_NOT_REGISTERED"
                primary_error_msg = primary_error_msg or "No online GSM gateway (gsm2sip / Android) or SIP trunk registered"
                checks.append({
                    "name": "gateway",
                    "status": "FAIL",
                    "code": "GSM_GATEWAY_NOT_REGISTERED",
                    "message": primary_error_msg,
                })
            else:
                checks.append({
                    "name": "gateway",
                    "status": "PASS",
                    "type": "SIP_TRUNK_ENV",
                    "trunk": os.getenv("OUTBOUND_TRUNK", "default"),
                })
        else:
            # Check channel capacity
            max_channels = getattr(gateway, "max_channels", 1) or 1
            if gateway.active_channels >= max_channels:
                is_ready = False
                primary_error_code = primary_error_code or "NO_TELEPHONY_CAPACITY"
                primary_error_msg = primary_error_msg or f"Gateway {gateway.name} capacity exhausted ({gateway.active_channels}/{max_channels})"
                checks.append({
                    "name": "gateway_capacity",
                    "status": "FAIL",
                    "code": "NO_TELEPHONY_CAPACITY",
                    "message": primary_error_msg,
                })
            else:
                checks.append({
                    "name": "gateway",
                    "status": "PASS",
                    "gateway_id": str(gateway.id),
                    "name": gateway.name,
                    "active_channels": gateway.active_channels,
                })

        return {
            "ready": is_ready,
            "mode": "LIVE",
            "normalized_phone": norm_phone,
            "resolved_caller_id": resolved_cid,
            "checks": checks,
            "error_code": primary_error_code,
            "error_message": primary_error_msg,
        }
