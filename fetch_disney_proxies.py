import itertools
import threading
import re

# Per-user proxy pools. Key = user_id (int). Admin uses ADMIN_ID as key.
_user_proxy_pools: dict = {}
_user_proxy_cycles: dict = {}
_user_uploaded_flags: dict = {}
_proxy_lock = threading.Lock()


# ============= PROXY PARSER =============

def _build_proxy_dict(scheme, host, port, user=None, password=None):
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if user is not None and password is not None:
        return f"{scheme}://{user}:{password}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


def _parse_proxy_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    line = re.sub(r"^([a-zA-Z][a-zA-Z0-9+.-]*):/+", r"\1://", line)
    line = re.sub(r"\s+", " ", line).strip()

    url_like = re.match(
        r"^(?P<scheme>https?|socks5h?|socks4a?)://"
        r"(?:(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@)?"
        r"(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$",
        line, flags=re.IGNORECASE,
    )
    if url_like:
        d = url_like.groupdict()
        return _build_proxy_dict(d["scheme"].lower(), d["host"], d["port"], d.get("user"), d.get("password"))

    m = re.match(r"^(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$", line)
    if m:
        d = m.groupdict()
        return _build_proxy_dict("http", d["host"], d["port"], d["user"], d["password"])

    m = re.match(r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)@(?P<user>[^:@\s]+):(?P<password>[^@\s]+)$", line)
    if m:
        d = m.groupdict()
        return _build_proxy_dict("http", d["host"], d["port"], d["user"], d["password"])

    m = re.match(r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$", line)
    if m:
        d = m.groupdict()
        return _build_proxy_dict("http", d["host"], d["port"])

    four = line.split(":")
    if len(four) == 4:
        a, b, c, d = four
        if b.isdigit() and not d.isdigit():
            return _build_proxy_dict("http", a, b, c, d)
        if d.isdigit() and not b.isdigit():
            return _build_proxy_dict("http", c, d, a, b)

    for pattern in [
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\s+(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\|(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+);(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+),(?P<user>[^:\s]+):(?P<password>\S+)$",
    ]:
        m = re.match(pattern, line)
        if m:
            d = m.groupdict()
            return _build_proxy_dict("http", d["host"], d["port"], d["user"], d["password"])

    return None


# ============= POOL HELPERS =============

def _set_pool(user_id, proxies: list):
    key = str(user_id)
    with _proxy_lock:
        _user_proxy_pools[key] = proxies
        _user_proxy_cycles[key] = itertools.cycle(proxies) if proxies else None


def get_pool_size(user_id) -> int:
    with _proxy_lock:
        return len(_user_proxy_pools.get(str(user_id), []))


def get_next_disney_proxy(user_id) -> str | None:
    key = str(user_id)
    with _proxy_lock:
        cycle = _user_proxy_cycles.get(key)
        if not cycle:
            return None
        return next(cycle)


def remove_disney_proxy(user_id, proxy_url: str):
    key = str(user_id)
    with _proxy_lock:
        pool = _user_proxy_pools.get(key, [])
        if proxy_url in pool:
            pool.remove(proxy_url)
            _user_proxy_pools[key] = pool
            _user_proxy_cycles[key] = itertools.cycle(pool) if pool else None
            print(f"[Proxy] Removed dead proxy for {user_id}. Pool: {len(pool)}")


def get_proxy_type_summary(user_id) -> str:
    with _proxy_lock:
        pool = _user_proxy_pools.get(str(user_id), [])
        if not pool:
            return "No proxies loaded"
        return _detect_types(pool)


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


def is_user_uploaded_pool(user_id) -> bool:
    return _user_uploaded_flags.get(str(user_id), False)


# ============= UPLOAD / CLEAR =============

def load_proxies_from_text(text: str) -> list[str]:
    return [p for line in text.splitlines() if (p := _parse_proxy_line(line))]


def load_proxies_from_file(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return load_proxies_from_text(f.read())
    except Exception as e:
        print(f"[Proxy] Failed to read file: {e}")
        return []


def set_uploaded_proxies(user_id, proxy_list: list[str]) -> int:
    """Store proxies for this user only. No other user is affected."""
    if not proxy_list:
        return 0
    _set_pool(user_id, proxy_list)
    _user_uploaded_flags[str(user_id)] = True
    print(f"[Proxy] Pool set for {user_id}: {len(proxy_list)} proxies")
    return len(proxy_list)


def clear_proxy_pool(user_id):
    """Clear only this user's proxy pool."""
    _set_pool(user_id, [])
    _user_uploaded_flags[str(user_id)] = False
    print(f"[Proxy] Pool cleared for {user_id}.")


# Mode → actual API endpoint to test against
_MODE_TEST_URLS = {
    "Crunchyroll": "https://api.crunchyroll.com/start.0.json",
    "Disney+":     "https://global.api.disneyplusbilling.com/",
    "Webtoon":     "https://www.webtoons.com/en/",
    "Vivamax":     "https://api.vivamax.ph/api/v6/auth/login",
    "Steam":       "https://store.steampowered.com/",
    "ExpressVPN":  "https://www.expressapisv2.net/",
    "Spotify":     "https://accounts.spotify.com/",
}
_DEFAULT_TEST_URL = "https://www.google.com"


def check_proxy_alive(proxy_url: str, mode: str = None, timeout: int = 4) -> bool:
    """
    Test a proxy against the actual endpoint for the given mode.
    Falls back to Google if mode is unknown.
    Uses HEAD to skip downloading a response body — much faster.
    Any HTTP response (even 401/403/503) means the proxy tunnelled successfully.
    """
    import requests
    test_url = _MODE_TEST_URLS.get(mode, _DEFAULT_TEST_URL)
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.head(
            test_url, proxies=proxies, timeout=timeout,
            allow_redirects=False, verify=False,
        )
        return resp.status_code < 599
    except requests.exceptions.SSLError:
        # SSL errors still mean the proxy connected — count as alive
        return True
    except Exception:
        return False


def test_all_proxies(
    user_id,
    mode: str = None,
    timeout: int = 4,
    progress_callback=None,
) -> dict:
    """
    Test every proxy in the user's pool against the real service endpoint.
    Returns {"alive": [...], "dead": [...], "mode": mode, "test_url": url}

    progress_callback(checked: int, total: int, is_alive: bool) — called after
    every completed proxy so callers can show live progress.

    Speed: 300 concurrent workers + 4s timeout.
    2 000 proxies → ~7 rounds × 4s ≈ 30s worst-case (was ~9 min with old 30-worker/8s setup).
    """
    import concurrent.futures

    key = str(user_id)
    with _proxy_lock:
        pool = list(_user_proxy_pools.get(key, []))

    if not pool:
        return {"alive": [], "dead": [], "mode": mode, "test_url": _DEFAULT_TEST_URL}

    test_url = _MODE_TEST_URLS.get(mode, _DEFAULT_TEST_URL)
    total = len(pool)

    def _check(proxy):
        return proxy, check_proxy_alive(proxy, mode=mode, timeout=timeout)

    alive, dead = [], []
    checked = 0
    workers = min(300, total)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_check, proxy): proxy for proxy in pool}
        for future in concurrent.futures.as_completed(futures):
            try:
                proxy, is_alive = future.result()
            except Exception:
                proxy = futures[future]
                is_alive = False

            if is_alive:
                alive.append(proxy)
            else:
                dead.append(proxy)

            checked += 1
            if progress_callback is not None:
                try:
                    progress_callback(checked, total, is_alive)
                except Exception:
                    pass

    return {"alive": alive, "dead": dead, "mode": mode, "test_url": test_url}


def remove_dead_proxies(user_id, dead_list: list) -> int:
    """Remove a specific list of dead proxies from the user's pool. Returns new pool size."""
    key = str(user_id)
    dead_set = set(dead_list)
    with _proxy_lock:
        pool = _user_proxy_pools.get(key, [])
        new_pool = [p for p in pool if p not in dead_set]
        _user_proxy_pools[key] = new_pool
        _user_proxy_cycles[key] = itertools.cycle(new_pool) if new_pool else None
    print(f"[Proxy] Removed {len(dead_list)} dead proxies for {user_id}. Remaining: {len(new_pool)}")
    return len(new_pool)
