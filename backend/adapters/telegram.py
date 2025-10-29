from fastapi import APIRouter, Request, HTTPException
from teleapi.httpx_transport import httpx_teleapi_factory
from backend.config import settings
from backend.utils.userManagement import read_user
from backend.utils.flags import is_telegram_bot_down
from backend.routers.index import read_main
from backend.db.database import get_session
from sqlmodel import Session

router = APIRouter()
bot = httpx_teleapi_factory(settings.TELEGRAM_BOT_KEY)


def get_db_session():
    return next(get_session())


async def process_message(message: dict):
    """Handle a Telegram message object from webhook"""
    if not message or "text" not in message:
        return

    chat_id = message["chat"]["id"]
    text = message["text"]
    user_contact_id = message["from"]["id"]

    session: Session = get_db_session()

    if is_telegram_bot_down():
        bot.sendMessage(chat_id=chat_id, text="Sorry, bot is temporarily down.")
        return

    try:
        user = read_user(str(user_contact_id), session)
        try:
            response = read_main(text, str(user_contact_id), session)
        except Exception as e:
            print("There was an error:", e)
            response = {"error": str(e)}

        response_text = response.get("message", "I received your message!")
        bot.sendMessage(chat_id=chat_id, text=response_text)
    except Exception as e:
        print("Error processing message:", e)
        bot.sendMessage(chat_id=chat_id, text="Sorry, I couldn't find you.")
    finally:
        session.close()


@router.post("/webhook")
async def telegram_webhook(request: Request):
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
async def set_webhook():
    """Manually set the Telegram webhook"""
    webhook_url = f"{settings.BASE_URL}/adapters/telegram/webhook"
    try:
        bot.setWebhook(url=webhook_url)
        return {"status": "Webhook set successfully", "url": webhook_url}
    except Exception as e:
        return {"status": "Failed", "error": str(e)}


@router.get("/delete-webhook")
async def delete_webhook():
    """Delete the Telegram webhook"""
    try:
        bot.deleteWebhook()
        return {"status": "Webhook deleted"}
    except Exception as e:
        return {"status": "Failed", "error": str(e)}
