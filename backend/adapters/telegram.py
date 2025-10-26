from fastapi import APIRouter, Depends, HTTPException, Header, Request
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
session = get_session()


async def set_webhook(url: str):
    response = bot.setWebhook(url=url, secret_token=settings.WEBHOOK_SECRET_TOKEN)
    print("Telegram webhook set:", response)


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
    update = await req.json()
    # print("Received update:", update)
    message = update.get("message")
    print("Message content:", message)

    if message and "text" in message:
        chat_id = message["chat"]["id"]
        text = message["text"]
        user_contact_id = message["from"]["id"]
        # send message that its temporarily down
        if is_telegram_bot_down():
            bot.sendMessage(chat_id=chat_id, text="Sorry, bot is temporarily down.")
            return {"ok": True}
        try:
            user = read_user(str(user_contact_id), session)
            response_text = f"Hello, {user.name}! You said: {text}"
            try:
                response = read_main(text, str(user_contact_id), session)
            except Exception as e:
                print("There was an error", e)
                response = {"error": str(e)}
            print("Response from read_main:", response)
            response_text = response.get("message", "I received your message!")
            print("Response message:", response_text)
            bot.sendMessage(
                chat_id=chat_id, text=response_text or "I received your message!"
            )
        except Exception as e:
            print("Error :", e)
            bot.sendMessage(chat_id=chat_id, text="Sorry, I couldn't find you.")
            return {"ok": True}

    return {"ok": True}


async def cleanup_bot():
    """Cleanup function to remove webhook on shutdown"""
    try:
        response = bot.deleteWebhook()
        print("Telegram webhook removed:", response)
    except Exception as e:
        print("Failed to remove Telegram webhook:", e)
