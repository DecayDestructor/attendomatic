from fastapi import APIRouter, Depends, Header, Request
from teleapi.httpx_transport import httpx_teleapi_factory
from backend.config import settings
from backend.utils.userManagement import read_user
from backend.utils.verify_secret_token import verify_secret_header
from backend.utils.flags import is_telegram_bot_down
from backend.routers.index import read_main
from backend.db.database import get_session
from sqlmodel import Session

bot = httpx_teleapi_factory(settings.TELEGRAM_BOT_KEY)
router = APIRouter()


async def set_webhook(url: str):
    try:
        response = bot.setWebhook(url=url, secret_token=settings.WEBHOOK_SECRET_TOKEN)
        print("✅ Telegram webhook set:", response)
    except Exception as e:
        print("❌ Failed to set Telegram webhook:", e)


def secret_token_dependency(
    secret_token: str = Header(alias="X-Telegram-Bot-Api-Secret-Token"),
):
    verify_secret_header(secret_token, settings.WEBHOOK_SECRET_TOKEN)


@router.post("/webhook")
async def telegram_webhook(
    req: Request,
    _=Depends(secret_token_dependency),
    session: Session = Depends(get_session),
):
    try:
        update = await req.json()
    except Exception as e:
        print("❌ Failed to parse request JSON:", e)
        return {"ok": True}

    message = update.get("message")
    print("📩 Message content:", message)

    if not message or "text" not in message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message["text"]
    user_contact_id = message["from"]["id"]

    try:
        if is_telegram_bot_down():
            bot.sendMessage(chat_id=chat_id, text="⚠️ Sorry, bot is temporarily down.")
            return {"ok": True}

        user = read_user(str(user_contact_id), session)

        try:
            response = read_main(text, str(user_contact_id), session)
            response_text = response.get("message", "✅ I received your message!")
        except Exception as e:
            print("❌ Error in read_main:", e)
            response_text = "⚠️ An internal error occurred."

        bot.sendMessage(chat_id=chat_id, text=response_text)

    except Exception as e:
        print("❌ Unhandled exception in webhook:", e)
        try:
            bot.sendMessage(chat_id=chat_id, text="⚠️ Sorry, something went wrong.")
        except Exception as inner_e:
            print("❌ Failed to send error message:", inner_e)

    return {"ok": True}


async def cleanup_bot():
    """Cleanup function to remove webhook on shutdown"""
    try:
        response = bot.deleteWebhook()
        print("🧹 Telegram webhook removed:", response)
    except Exception as e:
        print("❌ Failed to remove Telegram webhook:", e)
