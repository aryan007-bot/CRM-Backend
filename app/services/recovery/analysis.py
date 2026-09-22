import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.call import Call, TranscriptMessage
from app.db.models.call_analysis import CallAnalysis
from app.db.models.campaign import Campaign


class PostCallAnalysisService:
    @classmethod
    def analyze_call(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        call_id: uuid.UUID,
        force_reprocess: bool = False,
    ) -> CallAnalysis:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.organization_id == organization_id,
        )
        call = db.scalar(stmt)
        if not call:
            raise NotFoundException("Call not found", code="CALL_NOT_FOUND")

        # Check if existing analysis is present
        existing = db.scalar(
            select(CallAnalysis).where(
                CallAnalysis.call_id == call_id,
                CallAnalysis.organization_id == organization_id,
            )
        )
        if existing and not force_reprocess:
            return existing

        # Fetch transcripts
        transcripts = db.scalars(
            select(TranscriptMessage)
            .where(TranscriptMessage.call_id == call_id)
            .order_by(TranscriptMessage.timestamp.asc())
        ).all()

        full_text = " ".join((t.text for t in transcripts))
        lower_text = full_text.lower()

        # Sentiment heuristic
        sentiment = "neutral"
        if any(w in lower_text for w in ["thank you", "thanks", "sure", "happy to", "will pay", "cleared"]):
            sentiment = "positive"
        elif any(w in lower_text for w in ["cheat", "fraud", "police", "harass", "court", "lawyer", "idiot"]):
            sentiment = "hostile"
        elif any(w in lower_text for w in ["problem", "cannot pay", "difficult", "unemployed", "unable"]):
            sentiment = "negative"

        # Customer intent heuristic
        customer_intent = "unknown"
        if any(w in lower_text for w in ["will pay", "promise to pay", "send the link", "upi", "qr code", "tomorrow"]):
            customer_intent = "willing_to_pay"
        elif any(w in lower_text for w in ["already paid", "wrong amount", "not my loan", "never took", "dispute"]):
            customer_intent = "disputing"
        elif any(w in lower_text for w in ["call later", "next week", "busy right now", "traveling"]):
            customer_intent = "stalling"
        elif any(w in lower_text for w in ["wrong number", "don't call again", "leave me alone"]):
            customer_intent = "unavailable"
        elif sentiment == "hostile":
            customer_intent = "abusive"

        # Compliance auditing
        compliance_violations = []
        ai_transcripts = [t.text.lower() for t in transcripts if t.speaker == "ai"]
        ai_full = " ".join(ai_transcripts)

        campaign = db.get(Campaign, call.campaign_id) if call.campaign_id else None
        if campaign and campaign.ai_disclosure_enabled:
            if not any(w in ai_full for w in ["ai", "automated assistant", "virtual assistant", "artificial intelligence"]):
                compliance_violations.append("MISSING_AI_DISCLOSURE")

        if campaign and campaign.recording_disclosure_enabled:
            if not any(w in ai_full for w in ["recorded", "recording", "quality and training"]):
                compliance_violations.append("MISSING_RECORDING_DISCLOSURE")

        # Risk indicators
        risk_indicators = []
        if any(w in lower_text for w in ["lawyer", "police", "legal action", "court", "rbi complaint", "harassment"]):
            risk_indicators.append("LEGAL_THREAT_DETECTED")
        if any(w in lower_text for w in ["job loss", "hospital", "medical emergency", "bankrupt"]):
            risk_indicators.append("HARDSHIP_CLAIM")

        # Suggested next action
        suggested_action = "review"
        if customer_intent == "willing_to_pay":
            suggested_action = "send_payment_link"
        elif customer_intent == "disputing":
            suggested_action = "create_dispute_ticket"
        elif risk_indicators:
            suggested_action = "supervisor_review"
        elif customer_intent == "stalling":
            suggested_action = "schedule_callback"

        summary = (
            f"Call lasted {call.duration_seconds} seconds. "
            f"Customer intent assessed as '{customer_intent}' with '{sentiment}' sentiment. "
            f"{len(compliance_violations)} compliance flags."
        )

        analysis = existing or CallAnalysis(
            call_id=call_id,
            organization_id=organization_id,
        )
        analysis.sentiment = sentiment
        analysis.customer_intent = customer_intent
        analysis.key_points = {"transcript_count": len(transcripts), "duration": call.duration_seconds}
        analysis.risk_indicators = {"flags": risk_indicators}
        analysis.compliance_violations = {"violations": compliance_violations}
        analysis.suggested_next_action = suggested_action
        analysis.summary = summary
        analysis.confidence_score = Decimal("0.85")
        analysis.processed_at = datetime.now(timezone.utc)

        if not existing:
            db.add(analysis)

        db.commit()
        db.refresh(analysis)
        return analysis

    @classmethod
    def get_analysis(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        call_id: uuid.UUID,
    ) -> CallAnalysis:
        stmt = select(CallAnalysis).where(
            CallAnalysis.call_id == call_id,
            CallAnalysis.organization_id == organization_id,
        )
        analysis = db.scalar(stmt)
        if not analysis:
            raise NotFoundException("Call analysis not found", code="ANALYSIS_NOT_FOUND")
        return analysis

    @classmethod
    def get_by_id(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> CallAnalysis:
        stmt = select(CallAnalysis).where(
            (CallAnalysis.id == analysis_id) | (CallAnalysis.call_id == analysis_id),
            CallAnalysis.organization_id == organization_id,
        )
        analysis = db.scalar(stmt)
        if not analysis:
            raise NotFoundException("Call analysis not found", code="ANALYSIS_NOT_FOUND")
        return analysis

    @classmethod
    def list_analyses(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        sentiment: Optional[str] = None,
        intent: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ):
        from app.utils.pagination import paginate
        stmt = select(CallAnalysis).where(CallAnalysis.organization_id == organization_id)
        if sentiment:
            stmt = stmt.where(CallAnalysis.sentiment == sentiment)
        if intent:
            stmt = stmt.where(CallAnalysis.customer_intent == intent)

        stmt = stmt.order_by(CallAnalysis.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
