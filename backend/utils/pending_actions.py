from fastapi import Depends
from sqlmodel import Session, select
from datetime import datetime
from backend.db.database import get_session
from backend.db.models import PendingAction
from backend.routers.index import LLMMultiResponse


# CREATE
def create_pending_action(
    contact_id: str,
    review: LLMMultiResponse,
    confirmation_message: str,
    session: Session,
):
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


# READ
def get_pending_action(
    contact_id: str,
    session: Session,
):

    statement = select(PendingAction).where(
        PendingAction.contact_id == contact_id,
        PendingAction.status == "pending",
        PendingAction.expires_at > datetime.utcnow(),
    )

    return session.exec(statement).first()


# CONFIRM
def confirm_pending_action(
    pending: PendingAction,
    session: Session,
):

    pending.status = "confirmed"

    session.add(pending)
    session.commit()


# CANCEL
def cancel_pending_action(
    pending: PendingAction,
    session: Session,
):

    pending.status = "cancelled"

    session.add(pending)
    session.commit()
