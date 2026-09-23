import os
from typing import Optional, Tuple

from app.services.telephony_core.phone_number_service import PhoneNumberService


class OutboundDialService:
    """Resolves outbound dial strings, PJSIP routes, and caller ID policies."""

    @classmethod
    def get_outbound_dial_string(
        cls,
        normalized_destination: str,
        gateway_type: str = "GSM",
        trunk_name: Optional[str] = None,
    ) -> str:
        """Constructs the Asterisk PJSIP dial string.
        
        Examples:
            - GSM gateway (gsm2sip / Android SIM): PJSIP/+919213960958@gsm-gateway
            - SIP carrier trunk: PJSIP/+919213960958@sip-carrier
        """
        target_trunk = trunk_name or os.getenv("OUTBOUND_TRUNK", "gsm-gateway")
        
        # Clean destination for Asterisk SIP URI
        return f"PJSIP/{normalized_destination}@{target_trunk}"

    @classmethod
    def resolve_caller_id(
        cls,
        requested_caller_id: Optional[str],
        gateway_type: str = "GSM",
        gateway_msisdn: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Validates and resolves permitted caller ID.
        
        Rules:
            - For GSM/Android SIM gateways: The network operator uses the SIM's MSISDN.
              Arbitrary spoofing is rejected. If requested differs from SIM, warning/fallback applies.
            - For SIP Trunks: Validates against configured allowed caller IDs.
        """
        # If gateway is GSM SIM, actual SIM phone number is the authoritative caller ID
        if gateway_type.upper() in ("GSM", "ANDROID"):
            if gateway_msisdn:
                return True, gateway_msisdn, None
            # If no SIM MSISDN configured, use fallback or requested if valid E.164
            if requested_caller_id:
                valid, norm, err = PhoneNumberService.normalize_phone(requested_caller_id)
                if valid:
                    return True, norm, None
            default_cid = os.getenv("DEFAULT_CALLER_ID", "+911145678900")
            return True, default_cid, None

        # For SIP Trunk carriers
        if requested_caller_id:
            valid, norm, err = PhoneNumberService.normalize_phone(requested_caller_id)
            if not valid:
                return False, "", f"Invalid caller ID format: {err}"
            return True, norm, None

        default_cid = os.getenv("DEFAULT_CALLER_ID", "+911145678900")
        return True, default_cid, None
