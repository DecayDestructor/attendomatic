"""
Telegram adapter — webhook receiver and message handler.

Exposes endpoints to:
- Receive Telegram webhook updates  (POST /webhook)
- Register / delete the webhook URL  (GET /set-webhook, /delete-webhook)

Message flow:
1. Telegram sends an update to /webhook.
2. `process_message` checks for pending actions (yes/no confirmation).
3. If no pending action, the message is sent to the LLM via `read_main`.
4. A confirmation prompt is sent back to the user.
"""

from fastapi import APIRouter, Header, Request, HTTPException
from teleapi.httpx_transport import httpx_teleapi_factory
from backend.config import settings
from backend.utils.userManagement import read_user
from backend.utils.flags import is_telegram_bot_down
from backend.routers.index import read_main
from backend.db.database import get_session
from sqlmodel import Session

from backend.utils.verify_secret_token import verify_secret_header
from backend.utils.verify_secret_token import verify_api_secret

router = APIRouter()
bot = httpx_teleapi_factory(settings.TELEGRAM_BOT_KEY)  # Telegram bot API client


def get_db_session():
    """Create a one-off DB session (used outside of FastAPI dependency injection)."""
    return next(get_session())


from backend.utils.pending_actions import (
    create_pending_action,
    get_pending_action,
    confirm_pending_action,
    cancel_pending_action,
)
from backend.routers.index import LLMMultiResponse, perform_intent


async def process_message(message: dict):
    """
    Handle a single incoming Telegram message.

    - If the user has a pending action, treats the message as a yes/no confirmation.
    - Otherwise, sends the text through the LLM pipeline (read_main) and
      stores the result as a new pending action awaiting confirmation.
    """
    if not message or "text" not in message:
        return

    chat_id = message["chat"]["id"]
    text = message["text"]
    user_contact_id = message["from"]["id"]
    contact_id = str(user_contact_id)

    session: Session = get_db_session()

    if is_telegram_bot_down():
        bot.sendMessage(chat_id=chat_id, text="Sorry, bot is temporarily down.")
        return

    try:
        user = read_user(str(user_contact_id), session)
        print(f"Received message from user {user.name} ({user_contact_id}): {text}")

        # --- Check for an existing pending action (confirmation flow) ---
        get_pending = get_pending_action(str(user_contact_id), session)
        if get_pending:
            if text.lower() in ["yes", "y"]:
                confirm_pending_action(get_pending, session)
                print("Performing intent for pending action:", get_pending.intent_json)
                try:
                    message = perform_intent(
                        contact_id=get_pending.contact_id,
                        review=get_pending.intent_json,
                        session=session,
                    ).get("message", "Action performed successfully!")
                    bot.sendMessage(chat_id=chat_id, text=message)
                except Exception as e:
                    print("Error performing intent for pending action:", e)
                    bot.sendMessage(
                        chat_id=chat_id,
                        text="Sorry, there was an error performing the action.",
                    )
            else:
                cancel_pending_action(get_pending, session)
                bot.sendMessage(chat_id=chat_id, text="Action cancelled.")
            return
        # --- No pending action — run the message through the LLM pipeline ---
        try:
            response = read_main(text, str(user_contact_id), session)
            review = response.get("review")
            contact_id = response.get("contact_id")
        except Exception as e:
            print("There was an error:", e)
            response = {"error": str(e)}
        # Send the confirmation prompt back to the user
        response_text = response.get(
            "confirmation_message", "There was an error processing your request."
        )
        print(f"Sending response to user {contact_id}: {response_text}")
        bot.sendMessage(chat_id=chat_id, text=response_text)
        # User's next message will be handled by the pending-action branch above
    except Exception as e:
        print("Error processing message:", e)
        bot.sendMessage(chat_id=chat_id, text="Sorry, I couldn't find you.")
    finally:
        session.close()


def verify_telegram_secret(x_telegram_bot_api_secret_token: str = Header(None)):
    """Dependency that validates Telegram secret header"""
    verify_secret_header(
        header_value=x_telegram_bot_api_secret_token,
        expected_token=settings.WEBHOOK_SECRET_TOKEN,
    )


# import depends
from fastapi import Depends


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    _=Depends(verify_telegram_secret),
):
    """Receive updates directly from Telegram"""
    try:
        data = await request.json()
        print("Incoming Telegram webhook:", data)

        message = data.get("message")
        if message:
            await process_message(message)

        return {"ok": True}

    except Exception as e:
        print("Webhook error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/set-webhook")
async def set_webhook(_=Depends(verify_api_secret)):
    """Manually set the Telegram webhook (requires API key)"""
    webhook_url = f"{settings.BASE_URL}/adapters/telegram/webhook"
    try:
        bot.setWebhook(url=webhook_url, secret_token=settings.WEBHOOK_SECRET_TOKEN)
        return {"status": "Webhook set successfully", "url": webhook_url}
    except Exception as e:
        return {"status": "Failed", "error": str(e)}


@router.get("/delete-webhook")
async def delete_webhook(_=Depends(verify_api_secret)):
    """Delete the Telegram webhook (requires API key)"""
    try:
        bot.deleteWebhook()
        return {"status": "Webhook deleted"}
    except Exception as e:
        return {"status": "Failed", "error": str(e)}
