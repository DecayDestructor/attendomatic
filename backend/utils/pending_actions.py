"""
Pending action CRUD for the confirmation flow.

Before executing any LLM-parsed intent, the bot stores it as a PendingAction
(status='pending').  The user's next reply (yes/no) triggers confirm/cancel.
Pending actions expire automatically after 5 minutes.
"""

from fastapi import Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from backend.db.database import get_session
from backend.db.models import PendingAction
from backend.routers.index import LLMMultiResponse


def create_pending_action(
    contact_id: str,
    review: LLMMultiResponse,
    confirmation_message: str,
    session: Session,
):
    """Store a new pending action, cancelling any existing one for this user."""
    if not contact_id:
        raise HTTPException(status_code=400, detail="Missing contact_id")
    if not review:
        raise HTTPException(status_code=400, detail="Missing review (LLM response)")
    if not confirmation_message:
        raise HTTPException(status_code=400, detail="Missing confirmation_message")
    existing_pending = get_pending_action(contact_id, session)
    if existing_pending:
        print("Existing pending action found, cancelling it:", existing_pending)
        cancel_pending_action(existing_pending, session)

    pending = PendingAction(
        contact_id=contact_id,
        intent_json=review.model_dump(mode="json"),
        confirmation_message=confirmation_message,
        status="pending",
    )
    session.add(pending)
    session.commit()
    session.refresh(pending)

    return pending


def get_pending_action(
    contact_id: str,
    session: Session,
):
    """Return the active (non-expired) pending action for a user, or None."""
    if not contact_id:
        raise HTTPException(status_code=400, detail="Missing contact_id")

    statement = select(PendingAction).where(
        PendingAction.contact_id == contact_id,
        PendingAction.status == "pending",
        PendingAction.expires_at > datetime.utcnow(),
    )

    return session.exec(statement).first()


def confirm_pending_action(
    pending: PendingAction,
    session: Session,
):
    """Mark a pending action as confirmed (user replied yes)."""

    pending.status = "confirmed"

    session.add(pending)
    session.commit()


def cancel_pending_action(
    pending: PendingAction,
    session: Session,
):
    """Mark a pending action as cancelled (user replied no / timed out)."""

    pending.status = "cancelled"

    session.add(pending)
    session.commit()
