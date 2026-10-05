import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_creator.bot import bot

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Telegram Auto Creator Suite Starting...")
    print("🤖 Bot Creation via @BotFather")
    print("📢 Public Channel Creation with Usernames")
    print("🔀 Multi-Account Shuffling & Auto-Fade Quota")
    print("=" * 50)
    bot.run()
