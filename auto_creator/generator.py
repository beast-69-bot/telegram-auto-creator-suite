import re
import random
import string

def sanitize_username(base: str) -> str:
    """Removes invalid characters, keeps only lowercase alphanumeric and underscore."""
    clean = re.sub(r'[^a-zA-Z0-9_]', '', base).lower()
    return clean

def generate_bot_variations(base_name: str, base_username: str, count: int = 40):
    """
    Generates variations for bot names and usernames.
    Each bot username MUST end with 'bot' or '_bot'.
    Length between 5 and 32 chars.
    """
    raw_user = sanitize_username(base_username)
    # Strip trailing 'bot' or '_bot' from base to create fresh suffixes
    if raw_user.endswith('_bot'):
        core_user = raw_user[:-4]
    elif raw_user.endswith('bot'):
        core_user = raw_user[:-3]
    else:
        core_user = raw_user
    
    if len(core_user) < 3:
        core_user = (core_user + "app")[:10]

    # Style templates for bot names
    name_suffixes = [
        "Pro", "Official", "Hub", "AI", "Plus", "V1", "V2", "Fast", 
        "Instant", "Daily", "Prime", "Ultra", "Max", "Zone", "Link", 
        "Direct", "Central", "Corner", "Club", "Point", "Desk", "Network"
    ]
    
    # User suffix patterns (ending in 'bot')
    user_patterns = [
        "{core}_{i}_bot",
        "{core}_pro_{i}_bot",
        "{core}_v{i}_bot",
        "{core}_ai_{i}_bot",
        "{core}_hub_{i}_bot",
        "{core}_fast_{i}_bot",
        "{core}_official_{i}_bot",
        "{core}_plus_{i}_bot",
        "{core}_direct_{i}_bot",
        "{core}_ultra_{i}_bot",
        "the_{core}_{i}_bot",
        "real_{core}_{i}_bot",
        "{core}_{tag}_bot",
        "{core}_{tag}bot",
        "{core}{tag}_bot",
    ]

    results = []
    seen_usernames = set()
    
    i = 1
    while len(results) < count:
        for pat in user_patterns:
            tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
            u = pat.format(core=core_user, i=i, tag=tag)
            
            # Ensure valid length (5-32)
            if len(u) > 32:
                u = u[:28] + "_bot"
            
            if u not in seen_usernames and (u.endswith("bot") or u.endswith("_bot")):
                seen_usernames.add(u)
                
                # Pick a matching readable title name
                suffix = name_suffixes[(i - 1) % len(name_suffixes)]
                display_name = f"{base_name} {suffix} #{i}".strip()
                if len(display_name) > 64:
                    display_name = display_name[:60]
                
                results.append({
                    "name": display_name,
                    "username": u
                })
                
                if len(results) >= count:
                    break
        i += 1
        
    return results

def generate_channel_variations(base_title: str, base_username: str, count: int = 40):
    """
    Generates variations for public channel titles and usernames.
    Username length between 5 and 32 chars.
    """
    raw_user = sanitize_username(base_username)
    # Strip 'channel' if at end
    if raw_user.endswith('_channel'):
        core_user = raw_user[:-8]
    elif raw_user.endswith('channel'):
        core_user = raw_user[:-7]
    else:
        core_user = raw_user

    if len(core_user) < 3:
        core_user = (core_user + "net")[:10]

    title_suffixes = [
        "Official", "Hub", "Network", "Zone", "Central", "Daily", 
        "Community", "Direct", "Prime", "Corner", "Club", "Point",
        "Updates", "Alerts", "V1", "V2", "Pro", "Media", "Channel"
    ]
    
    user_patterns = [
        "{core}_{i}",
        "{core}_official_{i}",
        "{core}_hub_{i}",
        "{core}_channel_{i}",
        "{core}_daily_{i}",
        "{core}_zone_{i}",
        "{core}_network_{i}",
        "{core}_prime_{i}",
        "the_{core}_{i}",
        "real_{core}_{i}",
        "{core}_{tag}",
        "channel_{core}_{i}",
        "{core}_updates_{i}",
    ]

    results = []
    seen_usernames = set()
    
    i = 1
    while len(results) < count:
        for pat in user_patterns:
            tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
            u = pat.format(core=core_user, i=i, tag=tag)
            
            # Clean length
            if len(u) > 32:
                u = u[:30]
            if len(u) < 5:
                u = u + f"_{tag}"
                
            if u not in seen_usernames:
                seen_usernames.add(u)
                
                suffix = title_suffixes[(i - 1) % len(title_suffixes)]
                display_title = f"{base_title} {suffix} #{i}".strip()
                if len(display_title) > 64:
                    display_title = display_title[:60]
                
                results.append({
                    "title": display_title,
                    "username": u
                })
                
                if len(results) >= count:
                    break
        i += 1
        
    return results
