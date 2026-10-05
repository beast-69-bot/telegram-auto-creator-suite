import sqlite3
import datetime
import json
from auto_creator.config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Multiple user accounts table
    # owner_id: telegram user who controls the bot
    # phone: logged-in account phone number
    # bot_count: how many bots currently owned (max ~20)
    # channel_count: how many public channels owned (max ~10)
    # is_bot_quota_full: 1 if bot limit reached, else 0
    # is_channel_quota_full: 1 if channel limit reached, else 0
    c.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        phone TEXT UNIQUE,
        first_name TEXT,
        username TEXT,
        session_string TEXT,
        is_active INTEGER DEFAULT 1,
        bot_count INTEGER DEFAULT 0,
        channel_count INTEGER DEFAULT 0,
        is_bot_quota_full INTEGER DEFAULT 0,
        is_channel_quota_full INTEGER DEFAULT 0,
        status_note TEXT,
        created_at TIMESTAMP
    )
    """)
    
    # Task queue table
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        task_type TEXT, -- 'bot' or 'channel'
        base_name TEXT,
        base_username TEXT,
        description TEXT,
        about TEXT,
        pic_path TEXT,
        interval_seconds INTEGER,
        qty INTEGER,
        created_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending', -- 'pending', 'running', 'paused', 'completed', 'failed'
        last_run TIMESTAMP,
        error_message TEXT,
        created_at TIMESTAMP
    )
    """)
    
    # Created items log table
    c.execute("""
    CREATE TABLE IF NOT EXISTS created_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        owner_id INTEGER,
        account_id INTEGER,
        account_phone TEXT,
        item_type TEXT, -- 'bot' or 'channel'
        name TEXT,
        username TEXT,
        token TEXT,
        chat_id INTEGER,
        link TEXT,
        created_at TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

# Accounts management
def save_account(owner_id: int, phone: str, session_string: str, first_name: str = "", username: str = ""):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute("""
    INSERT INTO accounts (
        owner_id, phone, first_name, username, session_string, is_active, 
        is_bot_quota_full, is_channel_quota_full, created_at
    ) VALUES (?, ?, ?, ?, ?, 1, 0, 0, ?)
    ON CONFLICT(phone) DO UPDATE SET
        owner_id = excluded.owner_id,
        first_name = excluded.first_name,
        username = excluded.username,
        session_string = excluded.session_string,
        is_active = 1,
        created_at = excluded.created_at
    """, (owner_id, phone, first_name, username, session_string, now))
    conn.commit()
    conn.close()

def get_accounts_by_owner(owner_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM accounts WHERE owner_id = ? ORDER BY id ASC", (owner_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_account_by_id(account_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_available_accounts(owner_id: int, item_type: str = "bot"):
    """
    Returns active accounts that have not reached quota for the given item_type.
    """
    conn = get_connection()
    c = conn.cursor()
    if item_type == "bot":
        c.execute("""
        SELECT * FROM accounts 
        WHERE owner_id = ? AND is_active = 1 AND is_bot_quota_full = 0 AND bot_count < 20
        ORDER BY bot_count ASC, id ASC
        """, (owner_id,))
    else: # channel
        c.execute("""
        SELECT * FROM accounts 
        WHERE owner_id = ? AND is_active = 1 AND is_channel_quota_full = 0 AND channel_count < 10
        ORDER BY channel_count ASC, id ASC
        """, (owner_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_account_quota_full(account_id: int, item_type: str, reason: str = "Limit Reached"):
    """
    Fades / disables account for that specific type when quota is exhausted.
    """
    conn = get_connection()
    c = conn.cursor()
    if item_type == "bot":
        c.execute("""
        UPDATE accounts SET is_bot_quota_full = 1, status_note = ? WHERE id = ?
        """, (reason, account_id))
    else:
        c.execute("""
        UPDATE accounts SET is_channel_quota_full = 1, status_note = ? WHERE id = ?
        """, (reason, account_id))
    conn.commit()
    conn.close()

def increment_account_count(account_id: int, item_type: str):
    conn = get_connection()
    c = conn.cursor()
    if item_type == "bot":
        c.execute("UPDATE accounts SET bot_count = bot_count + 1 WHERE id = ?", (account_id,))
    else:
        c.execute("UPDATE accounts SET channel_count = channel_count + 1 WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

def delete_account(account_id: int, owner_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM accounts WHERE id = ? AND owner_id = ?", (account_id, owner_id))
    conn.commit()
    conn.close()

# Tasks
def create_task(owner_id: int, task_type: str, base_name: str, base_username: str, 
                description: str, about: str, pic_path: str, interval_seconds: int, qty: int):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute("""
    INSERT INTO tasks (
        owner_id, task_type, base_name, base_username, description, about, 
        pic_path, interval_seconds, qty, created_count, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending', ?)
    """, (owner_id, task_type, base_name, base_username, description, about, 
          pic_path, interval_seconds, qty, now))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_active_tasks():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE status IN ('pending', 'running') ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_task_by_id(task_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_task_progress(task_id: int, created_count: int, status: str = None, error_message: str = None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    if status:
        c.execute("""
        UPDATE tasks SET created_count = ?, status = ?, last_run = ?, error_message = ? WHERE id = ?
        """, (created_count, status, now, error_message, task_id))
    else:
        c.execute("""
        UPDATE tasks SET created_count = ?, last_run = ? WHERE id = ?
        """, (created_count, now, task_id))
    conn.commit()
    conn.close()

def log_created_item(task_id: int, owner_id: int, account_id: int, account_phone: str, 
                     item_type: str, name: str, username: str, 
                     token: str = None, chat_id: int = None, link: str = None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute("""
    INSERT INTO created_items (
        task_id, owner_id, account_id, account_phone, item_type, name, username, 
        token, chat_id, link, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, owner_id, account_id, account_phone, item_type, name, username, token, chat_id, link, now))
    conn.commit()
    conn.close()

def get_created_items_by_task(task_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM created_items WHERE task_id = ? ORDER BY id ASC", (task_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

init_db()
