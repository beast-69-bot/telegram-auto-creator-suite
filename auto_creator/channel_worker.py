import asyncio
import logging
from pyrogram import Client
from pyrogram.errors import (
    FloodWait, 
    UsernameOccupied, 
    UsernameInvalid, 
    RPCError
)
from auto_creator.config import API_ID, API_HASH

logger = logging.getLogger(__name__)

async def create_single_channel(session_string: str, title: str, username_candidates: list, 
                                description: str = None, pic_path: str = None):
    """
    Creates 1 public channel using user session.
    Returns:
    {
        "status": "success" | "quota_full" | "error" | "taken",
        "chat_id": int,
        "username": str,
        "link": str,
        "error": str
    }
    """
    app = Client(
        "channel_worker",
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
        # Step 1: Create Channel
        try:
            chat = await app.create_channel(
                title=title,
                description=description or ""
            )
            chat_id = chat.id
        except RPCError as e:
            err_str = str(e).upper()
            if "CHANNELS_ADMIN_PUBLIC_TOO_MANY" in err_str or "TOO_MUCH" in err_str or "TOO_MANY" in err_str:
                return {"status": "quota_full", "error": "Public channel limit reached (max 10 public channels)."}
            return {"status": "error", "error": f"Failed to create channel: {str(e)}"}

        # Step 2: Assign Public Username
        assigned_username = None
        for uname in username_candidates:
            try:
                await app.set_chat_username(chat_id=chat_id, username=uname)
                assigned_username = uname
                break
            except (UsernameOccupied, UsernameInvalid):
                await asyncio.sleep(0.5)
                continue
            except RPCError as e:
                err_str = str(e).upper()
                if "CHANNELS_ADMIN_PUBLIC_TOO_MANY" in err_str or "TOO_MUCH" in err_str or "TOO_MANY" in err_str:
                    return {"status": "quota_full", "error": "Public channel limit reached on this account."}
                logger.warning(f"Failed setting username {uname}: {err_str}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Failed setting username {uname}: {e}")
                await asyncio.sleep(0.5)

        if not assigned_username:
            return {"status": "taken", "error": "All generated channel usernames were taken or rejected."}

        # Step 3: Set Channel DP / Profile Photo
        if pic_path:
            try:
                await app.set_chat_photo(chat_id=chat_id, photo=pic_path)
            except Exception as e:
                logger.warning(f"Failed to set channel photo: {e}")

        link = f"https://t.me/{assigned_username}"

        return {
            "status": "success",
            "chat_id": chat_id,
            "username": assigned_username,
            "title": title,
            "link": link
        }

    except FloodWait as fw:
        return {"status": "error", "error": f"Telegram FloodWait: please wait {fw.value}s"}
    except Exception as e:
        return {"status": "error", "error": f"Channel creation error: {str(e)}"}
    finally:
        try:
            await app.stop()
        except Exception:
            pass
