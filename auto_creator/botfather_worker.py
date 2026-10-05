import asyncio
import re
import logging
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError
from auto_creator.config import API_ID, API_HASH

logger = logging.getLogger(__name__)

BOTFATHER = "BotFather"

TOKEN_REGEX = r"(\d{8,11}:[a-zA-Z0-9_-]{35})"

async def send_and_wait_reply(client: Client, chat_id: str, text: str, timeout: int = 15):
    """Sends a message to BotFather and waits for BotFather's reply."""
    # Record the last message ID before sending
    last_id = 0
    async for msg in client.get_chat_history(chat_id, limit=1):
        last_id = msg.id
        break

    await client.send_message(chat_id, text)
    
    # Wait for a new incoming message from chat_id
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        await asyncio.sleep(1.5)
        async for msg in client.get_chat_history(chat_id, limit=3):
            if msg.id > last_id and not msg.from_user.is_self:
                return msg
    return None

async def send_photo_and_wait_reply(client: Client, chat_id: str, photo_path: str, timeout: int = 20):
    """Sends a photo to BotFather and waits for reply."""
    last_id = 0
    async for msg in client.get_chat_history(chat_id, limit=1):
        last_id = msg.id
        break

    await client.send_photo(chat_id, photo_path)
    
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        await asyncio.sleep(1.5)
        async for msg in client.get_chat_history(chat_id, limit=3):
            if msg.id > last_id and not msg.from_user.is_self:
                return msg
    return None

async def create_single_bot(session_string: str, name: str, username_candidates: list, 
                            description: str = None, about: str = None, pic_path: str = None):
    """
    Creates 1 bot via @BotFather using user session.
    Returns:
    {
        "status": "success" | "quota_full" | "error" | "taken",
        "username": str,
        "token": str,
        "error": str
    }
    """
    app = Client(
        "botfather_worker",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True
    )
    
    try:
        await app.start()
    except Exception as e:
        return {"status": "error", "error": f"Session start failed: {str(e)}"}

    try:
        # Step 0: Cancel any pending action on BotFather
        await app.send_message(BOTFATHER, "/cancel")
        await asyncio.sleep(1)

        # Step 1: Send /newbot
        reply = await send_and_wait_reply(app, BOTFATHER, "/newbot")
        if not reply or not reply.text:
            return {"status": "error", "error": "BotFather did not respond to /newbot"}

        reply_text = reply.text.lower()
        if "limit" in reply_text or "too many" in reply_text or "maximum" in reply_text:
            return {"status": "quota_full", "error": "Bot limit reached on this account (max ~20)."}

        # Step 2: Send Bot Name
        reply = await send_and_wait_reply(app, BOTFATHER, name)
        if not reply or not reply.text:
            return {"status": "error", "error": "BotFather did not respond to bot name"}

        # Step 3: Try Usernames until one succeeds
        created_username = None
        bot_token = None

        for uname in username_candidates:
            logger.info(f"Trying bot username: {uname}")
            reply = await send_and_wait_reply(app, BOTFATHER, uname)
            if not reply or not reply.text:
                continue

            resp = reply.text
            # Check for success
            token_match = re.search(TOKEN_REGEX, resp)
            if token_match:
                created_username = uname
                bot_token = token_match.group(1)
                break
            
            # Check for username taken
            if "already taken" in resp.lower() or "occupied" in resp.lower() or "invalid" in resp.lower():
                await asyncio.sleep(1)
                continue
            
            # Check quota during username step
            if "limit" in resp.lower() or "too many" in resp.lower():
                return {"status": "quota_full", "error": "Bot limit reached on this account."}

        if not bot_token:
            await app.send_message(BOTFATHER, "/cancel")
            return {"status": "taken", "error": "All generated bot usernames were taken or rejected."}

        # Step 4: Set Description (What can this bot do? section)
        from auto_creator.config import DEFAULT_PROMO_TEXT
        final_desc = description if (description and description.strip()) else DEFAULT_PROMO_TEXT
        try:
            await send_and_wait_reply(app, BOTFATHER, "/setdescription")
            await asyncio.sleep(1)
            await send_and_wait_reply(app, BOTFATHER, f"@{created_username}")
            await asyncio.sleep(1)
            await send_and_wait_reply(app, BOTFATHER, final_desc[:512])
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Failed to set description: {e}")

        # Step 5: Set About text (Profile bio)
        if about:
            try:
                await send_and_wait_reply(app, BOTFATHER, "/setabouttext")
                await asyncio.sleep(1)
                await send_and_wait_reply(app, BOTFATHER, f"@{created_username}")
                await asyncio.sleep(1)
                await send_and_wait_reply(app, BOTFATHER, about[:120])
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to set about: {e}")

        # Step 6: Set Bot Pic (Profile photo)
        if pic_path:
            try:
                await send_and_wait_reply(app, BOTFATHER, "/setuserpic")
                await asyncio.sleep(1)
                await send_and_wait_reply(app, BOTFATHER, f"@{created_username}")
                await asyncio.sleep(1)
                await send_photo_and_wait_reply(app, BOTFATHER, pic_path)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to set user pic: {e}")

        return {
            "status": "success",
            "username": created_username,
            "token": bot_token,
            "name": name
        }

    except FloodWait as fw:
        return {"status": "error", "error": f"Telegram FloodWait: please wait {fw.value}s"}
    except Exception as e:
        return {"status": "error", "error": f"BotFather error: {str(e)}"}
    finally:
        try:
            await app.stop()
        except Exception:
            pass
