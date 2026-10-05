import asyncio
import logging
import random
from auto_creator.database import (
    get_task_by_id, 
    update_task_progress, 
    log_created_item, 
    get_available_accounts,
    mark_account_quota_full,
    increment_account_count
)
from auto_creator.generator import generate_bot_variations, generate_channel_variations
from auto_creator.botfather_worker import create_single_bot
from auto_creator.channel_worker import create_single_channel

logger = logging.getLogger(__name__)

# Active background runners map: task_id -> asyncio.Task
RUNNING_TASKS = {}

async def run_creation_task(task_id: int, bot_client):
    """
    Background worker that executes a bot or channel creation task
    using multi-account shuffling and time intervals.
    """
    task = get_task_by_id(task_id)
    if not task:
        return

    owner_id = task["owner_id"]
    task_type = task["task_type"]
    qty = task["qty"]
    interval = max(5, task["interval_seconds"])
    base_name = task["base_name"]
    base_username = task["base_username"]
    description = task["description"]
    about = task["about"]
    pic_path = task["pic_path"]
    
    update_task_progress(task_id, task["created_count"], status="running")

    try:
        await bot_client.send_message(
            owner_id,
            f"🚀 **Task #{task_id} Started!**\n\n"
            f"🎯 Type: `{task_type.upper()}`\n"
            f"📦 Target Quantity: `{qty}`\n"
            f"⏱️ Interval: `{interval}` seconds\n"
            f"🔀 Multi-Account Shuffling: **Enabled**"
        )
    except Exception:
        pass

    account_index = 0

    while True:
        task = get_task_by_id(task_id)
        if not task or task["status"] in ("paused", "failed"):
            break

        current_count = task["created_count"]
        if current_count >= qty:
            update_task_progress(task_id, current_count, status="completed")
            
            # Fetch all created items for this task
            items = get_created_items_by_task(task_id)
            
            # Generate export file
            import os
            from auto_creator.config import DATA_DIR
            report_file_path = os.path.join(DATA_DIR, f"task_{task_id}_{task_type}_summary.txt")
            
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(f"=====================================================\n")
                f.write(f"TASK #{task_id} SUMMARY REPORT - {task_type.upper()}S\n")
                f.write(f"Total Target: {qty} | Total Created: {len(items)}\n")
                f.write(f"Base Name: {base_name} | Base Username: {base_username}\n")
                f.write(f"=====================================================\n\n")
                
                for idx, itm in enumerate(items, 1):
                    if task_type == "bot":
                        f.write(f"[{idx}] {itm['name']}\n")
                        f.write(f"    Username: @{itm['username']}\n")
                        f.write(f"    Token:    {itm['token']}\n")
                        f.write(f"    Account:  {itm['account_phone']}\n")
                        f.write(f"    Created:  {itm['created_at']}\n\n")
                    else:
                        f.write(f"[{idx}] {itm['name']}\n")
                        f.write(f"    Link:     {itm['link']}\n")
                        f.write(f"    Username: @{itm['username']}\n")
                        f.write(f"    Account:  {itm['account_phone']}\n")
                        f.write(f"    Created:  {itm['created_at']}\n\n")

            # Send completion message & document to user and all admins
            from auto_creator.config import ADMIN_IDS
            recipients = set([owner_id] + ADMIN_IDS)
            
            for admin_chat_id in recipients:
                try:
                    caption = (
                        f"🎉 **TASK #{task_id} COMPLETED SUCCESSFULLY!**\n\n"
                        f"✅ **Total Created:** `{len(items)} / {qty}`\n"
                        f"🎯 **Type:** `{task_type.upper()}`\n"
                        f"👤 **Initiated By:** `{owner_id}`\n"
                        f"📁 *Detailed tokens and links list attached below!*"
                    )
                    await bot_client.send_document(
                        admin_chat_id,
                        document=report_file_path,
                        caption=caption
                    )
                except Exception as e:
                    logger.error(f"Error sending report file to admin {admin_chat_id}: {e}")
            break

        # Fetch available accounts (accounts where quota is not full)
        available_accounts = get_available_accounts(owner_id, item_type=task_type)
        if not available_accounts:
            update_task_progress(task_id, current_count, status="failed", 
                                 error_message="No active accounts available (all quotas reached).")
            try:
                await bot_client.send_message(
                    owner_id,
                    f"⚠️ **Task #{task_id} Paused / Stopped!**\n\n"
                    f"All connected accounts have reached their maximum {task_type} limit.\n"
                    f"Please login new accounts using `/login` to continue."
                )
            except Exception:
                pass
            break

        # Pick next account in round-robin / shuffle sequence
        account_index = account_index % len(available_accounts)
        current_account = available_accounts[account_index]
        account_index += 1

        acc_phone = current_account["phone"]
        session_str = current_account["session_string"]
        acc_id = current_account["id"]

        # Generate candidates for this iteration
        seed_num = current_count + 1
        if task_type == "bot":
            variations = generate_bot_variations(base_name, base_username, count=15)
            target_name = f"{base_name} #{seed_num}"
            username_candidates = [v["username"] for v in variations]

            logger.info(f"Task #{task_id}: Creating bot {seed_num}/{qty} on account {acc_phone}")
            res = await create_single_bot(
                session_string=session_str,
                name=target_name,
                username_candidates=username_candidates,
                description=description,
                about=about,
                pic_path=pic_path
            )

            if res["status"] == "quota_full":
                mark_account_quota_full(acc_id, "bot", res.get("error", "Bot limit reached"))
                try:
                    await bot_client.send_message(
                        owner_id,
                        f"⚠️ **Account Quota Reached!**\n"
                        f"📱 Phone: `{acc_phone}`\n"
                        f"Faded account from bot pool. Switching to remaining accounts..."
                    )
                except Exception:
                    pass
                continue # Retry same count with next account

            elif res["status"] == "success":
                new_count = current_count + 1
                increment_account_count(acc_id, "bot")
                log_created_item(
                    task_id=task_id,
                    owner_id=owner_id,
                    account_id=acc_id,
                    account_phone=acc_phone,
                    item_type="bot",
                    name=res["name"],
                    username=res["username"],
                    token=res["token"]
                )
                update_task_progress(task_id, new_count)

                # Send live alert to user
                try:
                    await bot_client.send_message(
                        owner_id,
                        f"✅ **Bot Created [{new_count}/{qty}]**\n\n"
                        f"🤖 **Username:** @{res['username']}\n"
                        f"🏷️ **Name:** {res['name']}\n"
                        f"🔑 **Token:** `{res['token']}`\n"
                        f"📱 **Account:** `{acc_phone}`\n\n"
                        f"⏳ Next creation in `{interval}s`..."
                    )
                except Exception:
                    pass

            else:
                logger.warning(f"Task #{task_id}: Bot creation attempt failed: {res.get('error')}")
                try:
                    await bot_client.send_message(
                        owner_id,
                        f"⚠️ Notice: Attempt failed for account `{acc_phone}` ({res.get('error')}). Will retry next."
                    )
                except Exception:
                    pass

        else: # Public Channel
            variations = generate_channel_variations(base_name, base_username, count=15)
            target_title = f"{base_name} #{seed_num}"
            username_candidates = [v["username"] for v in variations]

            logger.info(f"Task #{task_id}: Creating channel {seed_num}/{qty} on account {acc_phone}")
            res = await create_single_channel(
                session_string=session_str,
                title=target_title,
                username_candidates=username_candidates,
                description=description,
                pic_path=pic_path
            )

            if res["status"] == "quota_full":
                mark_account_quota_full(acc_id, "channel", res.get("error", "Channel limit reached"))
                try:
                    await bot_client.send_message(
                        owner_id,
                        f"⚠️ **Account Quota Reached!**\n"
                        f"📱 Phone: `{acc_phone}`\n"
                        f"Faded account from channel pool. Switching to remaining accounts..."
                    )
                except Exception:
                    pass
                continue

            elif res["status"] == "success":
                new_count = current_count + 1
                increment_account_count(acc_id, "channel")
                log_created_item(
                    task_id=task_id,
                    owner_id=owner_id,
                    account_id=acc_id,
                    account_phone=acc_phone,
                    item_type="channel",
                    name=res["title"],
                    username=res["username"],
                    chat_id=res["chat_id"],
                    link=res["link"]
                )
                update_task_progress(task_id, new_count)

                # Send live alert to user
                try:
                    await bot_client.send_message(
                        owner_id,
                        f"📢 **Channel Created [{new_count}/{qty}]**\n\n"
                        f"🏷️ **Title:** {res['title']}\n"
                        f"🔗 **Link:** {res['link']}\n"
                        f"📱 **Account:** `{acc_phone}`\n\n"
                        f"⏳ Next creation in `{interval}s`..."
                    )
                except Exception:
                    pass
            else:
                logger.warning(f"Task #{task_id}: Channel attempt failed: {res.get('error')}")

        # Sleep for specified interval
        await asyncio.sleep(interval)

    # Cleanup
    if task_id in RUNNING_TASKS:
        del RUNNING_TASKS[task_id]

def start_task_in_background(task_id: int, bot_client):
    """Schedules run_creation_task as an asyncio background task."""
    loop = asyncio.get_event_loop()
    t = loop.create_task(run_creation_task(task_id, bot_client))
    RUNNING_TASKS[task_id] = t
    return t
