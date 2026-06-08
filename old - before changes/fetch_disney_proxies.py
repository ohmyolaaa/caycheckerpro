import itertools
import threading
import requests as req
import re
import time

_disney_proxy_pool: list = []
_disney_proxy_cycle = None
_disney_proxy_lock = threading.Lock()
_disney_last_refreshed: float = 0.0
_is_user_uploaded: bool = False
_auto_refresh_enabled: bool = False  # OFF by default since we have manual control

# ============= ROBUST PROXY PARSER =============

def _build_proxy_dict(scheme, host, port, user=None, password=None):
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if user is not None and password is not None:
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
    else:
        proxy_url = f"{scheme}://{host}:{port}"
    return proxy_url


def _parse_proxy_line(line: str) -> str | None:
    """
    Parse proxy in any format:
      ip:port
      user:pass@ip:port
      ip:port@user:pass
      http://ip:port
      https://user:pass@ip:port
      socks4://ip:port
      socks5://user:pass@ip:port
      ip:port:user:pass
      user:pass:ip:port
      ip:port user:pass
      ip:port|user:pass
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Normalize slashes like http:///ip -> http://ip
    line = re.sub(r"^([a-zA-Z][a-zA-Z0-9+.-]*):/+", r"\1://", line)
    line = re.sub(r"\s+", " ", line).strip()

    # === URL with scheme (http, https, socks4, socks5) ===
    url_like = re.match(
        r"^(?P<scheme>https?|socks5h?|socks4a?)://"
        r"(?:(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@)?"
        r"(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$",
        line, flags=re.IGNORECASE,
    )
    if url_like:
        data = url_like.groupdict()
        return _build_proxy_dict(data["scheme"].lower(), data["host"], data["port"], data.get("user"), data.get("password"))

    userpass_hostport = re.match(
        r"^(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$", line)
    if userpass_hostport:
        data = userpass_hostport.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    hostport_userpass = re.match(
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)@(?P<user>[^:@\s]+):(?P<password>[^@\s]+)$", line)
    if hostport_userpass:
        data = hostport_userpass.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    # === host:port (plain) ===
    hostport = re.match(r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$", line)
    if hostport:
        data = hostport.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"])

    # === 4-part: host:port:user:pass or user:pass:host:port ===
    four_part = line.split(":")
    if len(four_part) == 4:
        a, b, c, d = four_part
        if b.isdigit() and not d.isdigit():
            return _build_proxy_dict("http", a, b, c, d)
        if d.isdigit() and not b.isdigit():
            return _build_proxy_dict("http", c, d, a, b)

    # === host:port with space, pipe, semicolon, comma separating user:pass ===
    split_patterns = [
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\s+(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\|(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+);(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+),(?P<user>[^:\s]+):(?P<password>\S+)$",
    ]
    for pattern in split_patterns:
        match = re.match(pattern, line)
        if match:
            data = match.groupdict()
            return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    return None


# ============= POOL HELPERS =============

def get_pool_size() -> int:
    with _disney_proxy_lock:
        return len(_disney_proxy_pool)


def get_next_disney_proxy() -> str | None:
    """Round-robin proxy rotation."""
    with _disney_proxy_lock:
        if not _disney_proxy_cycle:
            return None
        return next(_disney_proxy_cycle)


def _set_pool(proxies: list):
    """Thread-safe pool update."""
    global _disney_proxy_pool, _disney_proxy_cycle, _disney_last_refreshed
    with _disney_proxy_lock:
        _disney_proxy_pool = proxies
        _disney_proxy_cycle = itertools.cycle(proxies) if proxies else None
        _disney_last_refreshed = time.time()


def get_proxy_type_summary() -> str:
    with _disney_proxy_lock:
        if not _disney_proxy_pool:
            return "No proxies loaded"
        return _detect_types(_disney_proxy_pool)


def _detect_types(proxies: list[str]) -> str:
    types = set()
    for p in proxies:
        for scheme in ("socks5", "socks4", "https", "http"):
            if p.startswith(scheme + "://"):
                types.add(scheme.upper())
                break
        else:
            types.add("HTTP")
    return ", ".join(sorted(types)) if types else "Unknown"


def is_auto_refresh_enabled() -> bool:
    return _auto_refresh_enabled


def set_auto_refresh_enabled(enabled: bool):
    global _auto_refresh_enabled
    _auto_refresh_enabled = enabled
    print(f"[Proxy] Auto-refresh: {'ON' if enabled else 'OFF'}")


def is_user_uploaded_pool() -> bool:
    return _is_user_uploaded


# ============= UPLOAD PROXY =============

def load_proxies_from_text(text: str) -> list[str]:
    """
    Parse proxy list from uploaded .txt file content.
    Supports HTTP, HTTPS, SOCKS4, SOCKS5 and all common formats.
    Returns list of proxy URL strings.
    """
    parsed = []
    for line in text.splitlines():
        proxy_url = _parse_proxy_line(line)
        if proxy_url:
            parsed.append(proxy_url)
    return parsed


def load_proxies_from_file(filepath: str) -> list[str]:
    """Load and parse proxies from a local file path."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return load_proxies_from_text(f.read())
    except Exception as e:
        print(f"[Proxy] Failed to read file: {e}")
        return []


def set_uploaded_proxies(proxy_list: list[str]) -> int:
    global _is_user_uploaded
    if not proxy_list:
        return 0
    _set_pool(proxy_list)
    _is_user_uploaded = True
    print(f"[Proxy] Uploaded pool set: {len(proxy_list)} proxies ({_detect_types(proxy_list)})")
    return len(proxy_list)


def clear_proxy_pool():
    """Clear the pool entirely — used when user wants to reset."""
    global _is_user_uploaded
    _set_pool([])
    _is_user_uploaded = False
    print("[Proxy] Pool cleared.")


# ============= AUTO-FETCH FREE PROXIES =============

def fetch_disney_proxies():
    """Manually triggered or auto-refresh fetch from ProxyScrape."""
    global _is_user_uploaded
    try:
        print("[Proxy] Fetching free proxies...")
        headers = {
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        }
        resp = req.get(
            "https://api.proxynova.com/proxy/find?url=https%3A%2F%2Fproxyscrape.com%2Ffree-proxy-list",
            headers=headers, timeout=15
        )
        data = resp.json()
        raw_proxies = [
            f"{p['ip']}:{p['port']}-{i}"
            for i, p in enumerate(data.get("proxies", []))
        ]

        if not raw_proxies:
            print("[Proxy] No proxies fetched.")
            return

        print(f"[Proxy] Verifying {len(raw_proxies)} proxies...")
        files = [("ip_addr[]", (None, p)) for p in raw_proxies]
        check_headers = {
            "origin": "https://proxyscrape.com",
            "referer": "https://proxyscrape.com/",
            "user-agent": headers["user-agent"]
        }
        res = req.post(
            "https://api.proxyscrape.com/v4/online_check",
            headers=check_headers, files=files, timeout=30
        )
        live = [
            f"http://{p['ip']}:{p['port']}"
            for p in res.json() if p.get("working")
        ]

        _set_pool(live)
        _is_user_uploaded = False  # reset flag — this is an auto-fetch pool now
        print(f"[Proxy] {len(live)} live proxies ready.")

    except Exception as e:
        print(f"[Proxy] Fetch failed: {e}")


def refresh_disney_proxies_periodically():
    """Background thread — only refreshes if auto-refresh is ON and no user upload."""
    while True:
        time.sleep(30 * 60)
        if _auto_refresh_enabled and not _is_user_uploaded:
            fetch_disney_proxies()