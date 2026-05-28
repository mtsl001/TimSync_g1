"""
quick_token.py — Simple Fyers token generator
================================================
Uses auto TOTP+PIN for login, then extracts auth_code
from the redirect URL. Most reliable method.

Usage:  python quick_token.py
"""

import os, sys, json, base64, webbrowser
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    sys.exit("Install: pip install fyers-apiv3")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE  = os.path.join(SCRIPT_DIR, 'fyers_credentials.json')
TOKEN_FILE  = os.path.join(SCRIPT_DIR, 'fyers_token.json')
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'fyers_config.json')


def main():
    print("\n  ⚡ Quick Token Generator\n")

    # ── Load credentials ──
    if not os.path.exists(CREDS_FILE):
        sys.exit(f"  ✗ Run: python generate_token.py --setup")
    creds = json.load(open(CREDS_FILE))

    client_id    = creds['client_id']
    secret_key   = creds['secret_key']
    redirect_uri = creds.get('redirect_uri', 'https://trade.fyers.in/api-login/redirect-uri/index.html')

    # ── Check existing token ──
    if os.path.exists(TOKEN_FILE):
        token = json.load(open(TOKEN_FILE))
        if token.get('date') == str(date.today()):
            print(f"  ℹ Today's token exists ({token.get('generated_at')})")
            reuse = input("  Use existing? (Y/n): ").strip().lower()
            if reuse != 'n':
                verify(client_id, token['access_token'])
                return

    # ── Try full auto if TOTP credentials exist ──
    has_auto = all(creds.get(k) for k in ['fyers_id', 'pin', 'totp_key'])

    if has_auto:
        print("  Attempting auto-login...")
        auth_code = auto_get_authcode(creds, client_id, redirect_uri)
        if auth_code:
            token = exchange_token(client_id, secret_key, redirect_uri, auth_code)
            if token:
                save(client_id, token)
                verify(client_id, token)
                return
            print("  ⚠ Auto exchange failed, falling back to browser...\n")
        else:
            print("  ⚠ Auto auth_code failed, falling back to browser...\n")

    # ── Fallback: Browser login ──
    print("  Opening browser for login...")
    auth_session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        state="quick_token",
    )
    auth_url = auth_session.generate_authcode()
    print(f"  URL: {auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except:
        pass

    user_input = input("  Paste redirect URL or auth_code: ").strip()

    # Extract auth_code
    if 'auth_code=' in user_input:
        parsed = urlparse(user_input)
        auth_code = parse_qs(parsed.query).get('auth_code', [''])[0]
        if not auth_code:
            auth_code = parse_qs(parsed.fragment).get('auth_code', [''])[0]
    else:
        auth_code = user_input

    if not auth_code:
        sys.exit("  ✗ No auth_code found")

    token = exchange_token(client_id, secret_key, redirect_uri, auth_code)
    if token:
        save(client_id, token)
        verify(client_id, token)
    else:
        print("  ✗ Failed. Check redirect_uri matches your Fyers app settings.")


def auto_get_authcode(creds, client_id, redirect_uri):
    """Try fully automated TOTP+PIN flow to get auth_code."""
    try:
        import pyotp, requests
    except ImportError:
        print("  pip install pyotp requests")
        return None

    b64 = lambda s: base64.b64encode(str(s).encode()).decode()
    ses = requests.Session()

    try:
        # Step 1: OTP
        r1 = ses.post("https://api-t2.fyers.in/vagator/v2/send_login_otp_v2",
                       json={"fy_id": b64(creds['fyers_id']), "app_id": "2"}).json()
        if 'request_key' not in r1:
            return None
        print("    ✓ OTP sent")

        # Step 2: TOTP
        otp = pyotp.TOTP(creds['totp_key']).now()
        r2 = ses.post("https://api-t2.fyers.in/vagator/v2/verify_otp",
                       json={"request_key": r1["request_key"], "otp": otp}).json()
        if 'request_key' not in r2:
            return None
        print("    ✓ TOTP verified")

        # Step 3: PIN
        r3 = ses.post("https://api-t2.fyers.in/vagator/v2/verify_pin_v2",
                       json={"request_key": r2["request_key"],
                              "identity_type": "pin",
                              "identifier": b64(creds['pin'])}).json()
        if 'data' not in r3:
            return None
        print("    ✓ PIN verified")

        # Step 4: Get auth_code
        ses.headers.update({"Authorization": f"Bearer {r3['data']['access_token']}"})
        r4 = ses.post("https://api-t1.fyers.in/api/v3/token",
                       json={"fyers_id": creds['fyers_id'],
                              "app_id": client_id.split('-')[0],
                              "redirect_uri": redirect_uri,
                              "appType": "100",
                              "code_challenge": "",
                              "state": "None",
                              "scope": "",
                              "nonce": "",
                              "response_type": "code",
                              "create_cookie": True}).json()

        # Try multiple extraction methods
        # Method 1: Url field
        url = r4.get('Url') or r4.get('url', '')
        if url:
            auth_code = parse_qs(urlparse(url).query).get('auth_code', [''])[0]
            if auth_code:
                print("    ✓ Auth code (from Url)")
                return auth_code

        # Method 2: Follow redirect manually
        # Construct the URL that Fyers would redirect to
        data = r4.get('data', {})
        if data.get('auth'):
            # Try using the session to follow the authorization
            r5 = ses.get(
                f"https://api-t1.fyers.in/api/v3/token?auth_code={data['auth']}"
                f"&redirect_uri={redirect_uri}&state=None",
                allow_redirects=False
            )
            if r5.status_code in (301, 302, 303, 307):
                loc = r5.headers.get('Location', '')
                auth_code = parse_qs(urlparse(loc).query).get('auth_code', [''])[0]
                if auth_code:
                    print("    ✓ Auth code (from redirect)")
                    return auth_code

            # The auth field might itself work as auth_code for some app configs
            print(f"    ℹ Got data.auth (len={len(data['auth'])})")
            print(f"    ℹ App redirect: {data.get('redirectUrl', '?')}")
            print(f"    ℹ Our redirect: {redirect_uri}")

            # data.auth IS an auth_code (JWT with sub:"auth_code")
            # Try it directly
            print(f"    → Trying data.auth as auth_code...")
            return data['auth']

        print(f"    ✗ Unexpected response: {list(r4.keys())}")
        return None

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


def exchange_token(client_id, secret_key, redirect_uri, auth_code):
    """Exchange auth_code for access_token."""
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    session.set_token(auth_code)
    resp = session.generate_token()
    return resp.get('access_token')


def save(client_id, access_token):
    """Save token to files."""
    data = {
        'access_token': access_token,
        'client_id': client_id,
        'date': str(date.today()),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    json.dump(data, open(TOKEN_FILE, 'w'), indent=2)

    config = json.load(open(CONFIG_FILE)) if os.path.exists(CONFIG_FILE) else {}
    config['client_id'] = client_id
    config['access_token'] = access_token
    json.dump(config, open(CONFIG_FILE, 'w'), indent=2)
    print(f"  ✓ Token saved")


def verify(client_id, access_token):
    """Test token."""
    try:
        f = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")
        p = f.get_profile()
        if p.get('s') == 'ok':
            print(f"  ✓ Valid — {p['data'].get('name', '?')} ({p['data'].get('fy_id', '?')})")
        else:
            print(f"  ⚠ {p.get('message', 'Check app permissions on dashboard')}")
    except Exception as e:
        print(f"  ⚠ Verify error: {e}")


if __name__ == '__main__':
    main()