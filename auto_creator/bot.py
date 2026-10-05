import os
import sys
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from pyrogram.errors import (
    SessionPasswordNeeded, 
    PhoneCodeInvalid, 
    PasswordHashInvalid,
    FloodWait
)

# Set asyncio event loop for Python 3.14+
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from auto_creator.config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, PICS_DIR
from auto_creator.database import (
    save_account,
    get_accounts_by_owner,
    get_account_by_id,
    delete_account,
    create_task,
    get_active_tasks,
    get_created_items_by_task
)
from auto_creator.orchestrator import start_task_in_background, RUNNING_TASKS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AutoCreatorBot")

bot = Client(
    "auto_creator_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# User session temporary login state tracker:
# user_id -> { "step": str, "client": Client, "phone": str, "phone_code_hash": str }
LOGIN_SESSIONS = {}

# User wizard state tracker for createbot / createchannel
# user_id -> { "step": str, "type": "bot"|"channel", "data": dict }
WIZARDS = {}

def is_authorized(user_id: int) -> bool:
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS

# ----------------- KEYBOARDS -----------------

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 Create Bots", callback_data="wiz_bot"),
            InlineKeyboardButton("📢 Create Channels", callback_data="wiz_channel")
        ],
        [
            InlineKeyboardButton("📱 Manage Accounts", callback_data="menu_accounts"),
            InlineKeyboardButton("📊 Tasks Status", callback_data="menu_tasks")
        ],
        [
            InlineKeyboardButton("➕ Add New Account (/login)", callback_data="menu_login")
        ]
    ])

# ----------------- COMMANDS -----------------

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply_text("⛔ You are not authorized to use this bot.")
        return

    text = (
        f"👋 **Welcome to Auto Creator Suite!**\n\n"
        f"This bot automates creating **multiple Telegram Bots** (via @BotFather) "
        f"and **Public Channels** using your connected accounts.\n\n"
        f"✨ **Features:**\n"
        f"• Multi-Account Login & Storage\n"
        f"• Smart Account Shuffling / Round-Robin\n"
        f"• Auto-fading accounts when quota is reached\n"
        f"• Configurable Quantity (`qty`) and Time Intervals\n"
        f"• Random Unique Usernames based on your base reference\n"
        f"• Automatic Summary & Tokens File Delivery on completion\n\n"
        f"Choose an option below to get started:"
    )
    await message.reply_text(text, reply_markup=main_menu_keyboard())

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid in LOGIN_SESSIONS:
        try:
            await LOGIN_SESSIONS[uid]["client"].stop()
        except Exception:
            pass
        del LOGIN_SESSIONS[uid]
    
    if uid in WIZARDS:
        del WIZARDS[uid]

    await message.reply_text("❌ Current action/wizard has been cancelled.")

# ----------------- ACCOUNT LOGIN FLOW -----------------

@bot.on_message(filters.command("login") & filters.private)
async def login_start(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    uid = message.from_user.id
    # Clean previous login attempt if any
    if uid in LOGIN_SESSIONS:
        try:
            await LOGIN_SESSIONS[uid]["client"].stop()
        except Exception:
            pass
        del LOGIN_SESSIONS[uid]

    LOGIN_SESSIONS[uid] = {"step": "waiting_phone"}
    await message.reply_text(
        "📱 **Telegram Account Login**\n\n"
        "Please send your phone number with country code (e.g., `+919876543210`):\n\n"
        "*(Type /cancel to abort at any time)*"
    )

@bot.on_message(filters.command("accounts") & filters.private)
async def list_accounts_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return
    await show_accounts(client, message.chat.id, message.from_user.id)

async def show_accounts(client: Client, chat_id: int, owner_id: int):
    accounts = get_accounts_by_owner(owner_id)
    if not accounts:
        text = "📱 **No accounts connected yet!**\nUse `/login` to add your first Telegram account."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Account", callback_data="menu_login")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_home")]
        ])
        await client.send_message(chat_id, text, reply_markup=kb)
        return

    text = "📱 **Connected Telegram Accounts:**\n\n"
    buttons = []

    for acc in accounts:
        bot_status = "🔴 Full" if acc["is_bot_quota_full"] else f"🟢 {acc['bot_count']}/20"
        chan_status = "🔴 Full" if acc["is_channel_quota_full"] else f"🟢 {acc['channel_count']}/10"
        name = acc["first_name"] or "User"

        text += (
            f"👤 **{name}** (`{acc['phone']}`)\n"
            f"• Bots: {bot_status}\n"
            f"• Channels: {chan_status}\n"
        )
        if acc["status_note"]:
            text += f"• Note: _{acc['status_note']}_\n"
        text += "\n"

        buttons.append([
            InlineKeyboardButton(f"🗑️ Remove {acc['phone']}", callback_data=f"del_acc_{acc['id']}")
        ])

    buttons.append([
        InlineKeyboardButton("➕ Add Another Account", callback_data="menu_login"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_home")
    ])

    await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(buttons))

# ----------------- WIZARD STARTERS -----------------

@bot.on_message(filters.command("createbot") & filters.private)
async def createbot_cmd(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return
    await start_bot_wizard(client, message.chat.id, message.from_user.id)

@bot.on_message(filters.command("createchannel") & filters.private)
async def createchannel_cmd(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return
    await start_channel_wizard(client, message.chat.id, message.from_user.id)

async def start_bot_wizard(client: Client, chat_id: int, owner_id: int):
    # Check if user has accounts
    accounts = get_accounts_by_owner(owner_id)
    if not accounts:
        await client.send_message(
            chat_id, 
            "⚠️ You must connect at least 1 Telegram account first using `/login`!"
        )
        return

    WIZARDS[owner_id] = {
        "step": "base_name",
        "type": "bot",
        "data": {}
    }
    await client.send_message(
        chat_id,
        "🤖 **Create Bots Wizard**\n\n"
        "**Step 1/7:** Send the **Base Display Name** for your bots.\n"
        "*(Example: `Viral Video Saver`)*\n\n"
        "Type /cancel to abort."
    )

async def start_channel_wizard(client: Client, chat_id: int, owner_id: int):
    accounts = get_accounts_by_owner(owner_id)
    if not accounts:
        await client.send_message(
            chat_id, 
            "⚠️ You must connect at least 1 Telegram account first using `/login`!"
        )
        return

    WIZARDS[owner_id] = {
        "step": "base_name",
        "type": "channel",
        "data": {}
    }
    await client.send_message(
        chat_id,
        "📢 **Create Public Channels Wizard**\n\n"
        "**Step 1/6:** Send the **Base Title** for your channels.\n"
        "*(Example: `Viral Movies Network`)*\n\n"
        "Type /cancel to abort."
    )

# ----------------- MESSAGE DISPATCHER (LOGIN & WIZARDS) -----------------

@bot.on_message(filters.private & ~filters.command(["start", "login", "cancel", "accounts", "createbot", "createchannel", "status"]))
async def message_input_handler(client: Client, message: Message):
    uid = message.from_user.id
    if not is_authorized(uid):
        return

    # 1. Handle Login Steps
    if uid in LOGIN_SESSIONS:
        state = LOGIN_SESSIONS[uid]
        step = state["step"]

        if step == "waiting_phone":
            phone = message.text.strip().replace(" ", "")
            if not phone.startswith("+") or not phone[1:].isdigit():
                await message.reply_text("❌ Invalid format. Please include '+' and country code (e.g. `+919876543210`).")
                return

            await message.reply_text("⏳ Connecting and requesting login code...")
            user_client = Client(
                f"session_login_{uid}",
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True
            )
            try:
                await user_client.connect()
                code_data = await user_client.send_code(phone)
                state["client"] = user_client
                state["phone"] = phone
                state["phone_code_hash"] = code_data.phone_code_hash
                state["step"] = "waiting_code"
                await message.reply_text(
                    f"📩 **Telegram Login Code Sent to {phone}!**\n\n"
                    "Please send the login code here.\n"
                    "💡 *Tip: Put spaces between digits (e.g. `1 2 3 4 5`) so Telegram doesn't block it.*"
                )
            except Exception as e:
                logger.error(f"Login send_code error: {e}")
                await message.reply_text(f"❌ Failed to send code: `{str(e)}`\nTry again with /login.")
                try:
                    await user_client.disconnect()
                except Exception:
                    pass
                del LOGIN_SESSIONS[uid]
            return

        elif step == "waiting_code":
            raw_code = message.text.strip().replace(" ", "").replace("-", "")
            user_client = state["client"]
            phone = state["phone"]
            phone_code_hash = state["phone_code_hash"]

            try:
                await user_client.sign_in(phone, phone_code_hash, raw_code)
                # Success! Export session string
                session_str = await user_client.export_session_string()
                me = await user_client.get_me()
                
                save_account(
                    owner_id=uid,
                    phone=phone,
                    session_string=session_str,
                    first_name=me.first_name or "",
                    username=me.username or ""
                )
                
                await message.reply_text(
                    f"✅ **Account Connected Successfully!**\n\n"
                    f"👤 **Name:** {me.first_name}\n"
                    f"📱 **Phone:** `{phone}`\n"
                    f"🆔 **User ID:** `{me.id}`\n\n"
                    f"You can now use `/createbot` or `/createchannel`!",
                    reply_markup=main_menu_keyboard()
                )
                await user_client.disconnect()
                del LOGIN_SESSIONS[uid]
                return

            except SessionPasswordNeeded:
                state["step"] = "waiting_password"
                await message.reply_text(
                    "🔐 **Two-Step Verification (2FA) is enabled!**\n\n"
                    "Please send your 2FA Cloud Password:"
                )
                return
            except PhoneCodeInvalid:
                await message.reply_text("❌ Invalid code. Please enter the correct code:")
                return
            except Exception as e:
                await message.reply_text(f"❌ Login error: `{str(e)}`\nAborting login. Use /login to try again.")
                try:
                    await user_client.disconnect()
                except Exception:
                    pass
                del LOGIN_SESSIONS[uid]
                return

        elif step == "waiting_password":
            password = message.text.strip()
            user_client = state["client"]
            phone = state["phone"]

            try:
                await user_client.check_password(password)
                session_str = await user_client.export_session_string()
                me = await user_client.get_me()

                save_account(
                    owner_id=uid,
                    phone=phone,
                    session_string=session_str,
                    first_name=me.first_name or "",
                    username=me.username or ""
                )

                await message.reply_text(
                    f"✅ **Account Connected Successfully (2FA Verified)!**\n\n"
                    f"👤 **Name:** {me.first_name}\n"
                    f"📱 **Phone:** `{phone}`\n\n"
                    f"You can now use `/createbot` or `/createchannel`!",
                    reply_markup=main_menu_keyboard()
                )
                await user_client.disconnect()
                del LOGIN_SESSIONS[uid]
                return
            except PasswordHashInvalid:
                await message.reply_text("❌ Incorrect 2FA Password. Please send the correct password:")
                return
            except Exception as e:
                await message.reply_text(f"❌ Password error: `{str(e)}`")
                try:
                    await user_client.disconnect()
                except Exception:
                    pass
                del LOGIN_SESSIONS[uid]
                return

    # 2. Handle Creation Wizards
    if uid in WIZARDS:
        wiz = WIZARDS[uid]
        step = wiz["step"]
        wtype = wiz["type"]
        data = wiz["data"]

        if step == "base_name":
            data["base_name"] = message.text.strip()
            wiz["step"] = "base_username"
            await message.reply_text(
                f"**Step 2:** Send the **Base Reference Username**.\n"
                f"*(Variations will be automatically generated from this)*\n"
                f"Example: `{data['base_name'].lower().replace(' ', '_')[:15]}`"
            )
            return

        elif step == "base_username":
            data["base_username"] = message.text.strip().replace("@", "")
            wiz["step"] = "description"
            await message.reply_text(
                "**Step 3:** Send the **Description**.\n\n"
                "💡 *Type `/default` or `/skip` to automatically use the default MOD DOWNLOAD LINKS promo text!*"
            )
            return

        elif step == "description":
            txt = message.text.strip()
            from auto_creator.config import DEFAULT_PROMO_TEXT
            if txt in ("/skip", "/default", ""):
                data["description"] = DEFAULT_PROMO_TEXT
            else:
                data["description"] = txt
            
            if wtype == "bot":
                wiz["step"] = "about"
                await message.reply_text(
                    "**Step 4:** Send the **About Text** (short bio in bot profile, max 120 chars).\n"
                    "*(Or type `/skip` to skip)*"
                )
            else:
                wiz["step"] = "pic"
                await message.reply_text(
                    "**Step 4:** Send the **Profile Picture / DP** (as photo).\n"
                    "*(Or type `/skip` to skip)*"
                )
            return

        elif step == "about" and wtype == "bot":
            txt = message.text.strip()
            data["about"] = "" if txt == "/skip" else txt
            wiz["step"] = "pic"
            await message.reply_text(
                "**Step 5:** Send the **Bot Profile Picture / DP** (send a photo).\n"
                "*(Or type `/skip` to skip)*"
            )
            return

        elif step == "pic":
            pic_path = None
            if message.photo:
                # Download photo
                filename = f"pic_{uid}_{os.urandom(4).hex()}.jpg"
                dest = os.path.join(PICS_DIR, filename)
                await message.download(dest)
                pic_path = dest
            elif message.text and message.text.strip() == "/skip":
                pic_path = None
            else:
                await message.reply_text("Please send an actual photo or type `/skip`.")
                return

            data["pic_path"] = pic_path
            wiz["step"] = "qty"
            total_step = "6" if wtype == "bot" else "5"
            await message.reply_text(
                f"**Step {total_step}:** Send the **Quantity (Qty)** of {wtype}s to create.\n"
                f"*(Example: `20` for bots or `10` for channels)*"
            )
            return

        elif step == "qty":
            if not message.text or not message.text.strip().isdigit():
                await message.reply_text("❌ Please enter a valid number (e.g. `10` or `20`).")
                return
            qty = int(message.text.strip())
            if qty <= 0 or qty > 200:
                await message.reply_text("❌ Quantity must be between 1 and 200.")
                return

            data["qty"] = qty
            wiz["step"] = "interval"
            await message.reply_text(
                "**Final Step:** Send the **Time Interval (in seconds)** between creations.\n"
                "*(Recommended: `15` to `60` seconds to avoid Telegram rate limits)*"
            )
            return

        elif step == "interval":
            if not message.text or not message.text.strip().isdigit():
                await message.reply_text("❌ Please enter seconds as a number (e.g. `20`).")
                return
            interval = int(message.text.strip())
            if interval < 5:
                interval = 5

            data["interval_seconds"] = interval

            # Create task in DB
            task_id = create_task(
                owner_id=uid,
                task_type=wtype,
                base_name=data["base_name"],
                base_username=data["base_username"],
                description=data.get("description", ""),
                about=data.get("about", ""),
                pic_path=data.get("pic_path"),
                interval_seconds=interval,
                qty=data["qty"]
            )

            del WIZARDS[uid]

            # Start background execution
            start_task_in_background(task_id, bot)

            await message.reply_text(
                f"✅ **Task #{task_id} Created & Started!**\n\n"
                f"🎯 **Type:** `{wtype.upper()}`\n"
                f"🏷️ **Base Name:** {data['base_name']}\n"
                f"🔗 **Base Username:** @{data['base_username']}\n"
                f"📦 **Quantity:** `{data['qty']}`\n"
                f"⏱️ **Interval:** `{interval}s`\n"
                f"🖼️ **Photo:** {'Yes' if data.get('pic_path') else 'None'}\n\n"
                f"You will receive live updates as each {wtype} is created.\n"
                f"When completed, a complete summary document will be sent to you!",
                reply_markup=main_menu_keyboard()
            )
            return

# ----------------- CALLBACK QUERIES -----------------

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    uid = query.from_user.id
    chat_id = query.message.chat.id

    if not is_authorized(uid):
        await query.answer("Unauthorized", show_alert=True)
        return

    if data == "menu_home":
        await query.message.edit_text(
            "🏠 **Main Menu:**",
            reply_markup=main_menu_keyboard()
        )
        await query.answer()

    elif data == "menu_login":
        await query.answer()
        LOGIN_SESSIONS[uid] = {"step": "waiting_phone"}
        await query.message.reply_text(
            "📱 **Telegram Account Login**\n\n"
            "Please send your phone number with country code (e.g., `+919876543210`):\n\n"
            "*(Type /cancel to abort)*"
        )

    elif data == "menu_accounts":
        await query.answer()
        await show_accounts(client, chat_id, uid)

    elif data == "wiz_bot":
        await query.answer()
        await start_bot_wizard(client, chat_id, uid)

    elif data == "wiz_channel":
        await query.answer()
        await start_channel_wizard(client, chat_id, uid)

    elif data.startswith("del_acc_"):
        acc_id = int(data.split("_")[2])
        delete_account(acc_id, uid)
        await query.answer("Account removed!")
        await show_accounts(client, chat_id, uid)

    elif data == "menu_tasks":
        await query.answer()
        active = get_active_tasks()
        if not active:
            await query.message.reply_text("ℹ️ No active tasks running right now.")
            return

        text = "📊 **Active Tasks:**\n\n"
        for t in active:
            text += (
                f"• **Task #{t['id']}** ({t['task_type'].upper()})\n"
                f"  Progress: `{t['created_count']} / {t['qty']}`\n"
                f"  Status: `{t['status']}`\n"
                f"  Interval: `{t['interval_seconds']}s`\n\n"
            )
        await query.message.reply_text(text)

async def setup_commands():
    from pyrogram.types import BotCommand
    commands = [
        BotCommand("start", "Main dashboard & menu"),
        BotCommand("login", "Connect a new Telegram account"),
        BotCommand("accounts", "Manage connected accounts & quotas"),
        BotCommand("createbot", "Auto-create bots via @BotFather"),
        BotCommand("createchannel", "Auto-create public channels"),
        BotCommand("status", "Check running tasks progress"),
        BotCommand("cancel", "Cancel ongoing wizard/action")
    ]
    try:
        await bot.set_bot_commands(commands)
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

if __name__ == "__main__":
    print("Starting Auto Creator Bot...")
    bot.run()
