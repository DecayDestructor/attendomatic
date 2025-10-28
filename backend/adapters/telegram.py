from fastapi import APIRouter
from teleapi.httpx_transport import httpx_teleapi_factory
from backend.config import settings
from backend.utils.userManagement import read_user
from backend.utils.flags import is_telegram_bot_down
from backend.routers.index import read_main
from backend.db.database import get_session
from sqlmodel import Session
import asyncio

bot = httpx_teleapi_factory(settings.TELEGRAM_BOT_KEY)
router = APIRouter()


# We won't use a single global session object for safety;
# instead, create a new session per task when needed.
def get_db_session():
    return next(get_session())


async def process_message(message):
    """Process each incoming Telegram message (Message object from teleapi)"""
    if not message or not message.text:
        return

    chat_id = message.chat.id
    text = message.text
    user_contact_id = message.from_.id

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


async def poll_updates():
    """Continuously polls Telegram for new updates"""
    offset = 0
    print("Starting Telegram polling loop...")

    while True:
        try:
            updates = bot.getUpdates(offset=offset, timeout=10)
            if not updates:
                await asyncio.sleep(1)
                continue

            print(f"Polled updates: {updates}")

            for update in updates:
                offset = update.update_id + 1
                message = update.message
                if message:
                    await process_message(message)

        except Exception as e:
            print("Polling error:", e)
            await asyncio.sleep(5)

        await asyncio.sleep(1)


@router.on_event("startup")
async def start_polling():
    """Removes webhook and starts polling on app startup"""
    try:
        bot.deleteWebhook()
        print("Removed Telegram webhook before starting polling.")
    except Exception as e:
        print("Failed to remove webhook:", e)

    asyncio.create_task(poll_updates())
    print("Polling task started.")


@router.get("/telegram/status")
async def telegram_status():
    """For uptime pings or debugging"""
    return {"status": "Telegram bot polling is active"}
