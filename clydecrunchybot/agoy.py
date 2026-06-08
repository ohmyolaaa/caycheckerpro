import requests

email = "crewspains@gmail.com"
password = "Nim5fa1q!G"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://accounts.spotify.com',
    'Referer': 'https://accounts.spotify.com/login',
})

# Step 1: Get CSRF token
login_page = session.get('https://accounts.spotify.com/login', timeout=15)
csrf_token = session.cookies.get('csrf_token', '')
print(f"csrf_token: {csrf_token[:20] if csrf_token else 'MISSING'}")

# Step 2: Login
login_resp = session.post(
    'https://accounts.spotify.com/api/login',
    data={
        'remember': 'false',
        'username': email,
        'password': password,
        'csrf_token': csrf_token,
    },
    headers={'Content-Type': 'application/x-www-form-urlencoded'},
    timeout=15
)
print(f"login status={login_resp.status_code}")
print(f"login body={login_resp.text[:300]}")
print(f"sp_dc cookie: {session.cookies.get('sp_dc', 'MISSING')}")

# Step 3: Get access token
if session.cookies.get('sp_dc'):
    token_resp = session.get(
        'https://open.spotify.com/get_access_token?reason=transport&productType=web_player',
        timeout=15
    )
    print(f"token status={token_resp.status_code}")
    print(f"token body={token_resp.text[:200]}")