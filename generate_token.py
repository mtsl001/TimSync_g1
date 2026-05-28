"""
generate_token.py — Fyers Access Token Generator
====================================================
Two modes:
  1. MANUAL  (default) — Opens browser, you login, paste the auth_code
  2. AUTO    (--auto)  — Fully automated using TOTP key + PIN (no browser)

Fyers tokens expire daily. Run this every morning before trading.

Usage:
  python generate_token.py                  # Manual mode (browser)
  python generate_token.py --auto           # Automated mode (TOTP)
  python generate_token.py --setup          # First-time credential setup

Prerequisites:
  pip install fyers-apiv3 pyotp requests
  Create an app at: https://myapi.fyers.in/dashboard/
"""

import os
import sys
import json
import base64
import argparse
import webbrowser
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    print("  ✗ fyers_apiv3 not installed. Run: pip install fyers-apiv3")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE   = os.path.join(SCRIPT_DIR, 'fyers_credentials.json')
TOKEN_FILE   = os.path.join(SCRIPT_DIR, 'fyers_token.json')
CONFIG_FILE  = os.path.join(SCRIPT_DIR, 'fyers_config.json')

BANNER = """
  ⚡ Fyers Access Token Generator
  ═══════════════════════════════════
"""


def load_credentials() -> dict:
    """Load saved credentials."""
    if os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_credentials(creds: dict):
    with open(CREDS_FILE, 'w') as f:
        json.dump(creds, f, indent=2)
    print(f"  ✓ Credentials saved to {CREDS_FILE}")
    print(f"  ⚠ Keep this file safe — it contains your API secrets!\n")


def load_token() -> dict:
    """Load saved token (checks if today's token exists)."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            data = json.load(f)
        if data.get('date') == str(date.today()):
            return data
    return {}


def save_token(access_token: str, client_id: str):
    data = {
        'access_token': access_token,
        'client_id':    client_id,
        'date':         str(date.today()),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    # Also update fyers_config.json so the trading engine uses it
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    config['client_id'] = client_id
    config['access_token'] = access_token
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"  ✓ Token saved to {TOKEN_FILE}")
    print(f"  ✓ Config updated in {CONFIG_FILE}")


def verify_token(client_id: str, access_token: str) -> bool:
    """Test the token by fetching profile."""
    try:
        fyers = fyersModel.FyersModel(
            client_id=client_id, is_async=False,
            token=access_token, log_path=""
        )
        profile = fyers.get_profile()
        if profile.get('s') == 'ok':
            name = profile.get('data', {}).get('name', 'User')
            fy_id = profile.get('data', {}).get('fy_id', '')
            print(f"\n  ✓ TOKEN VALID")
            print(f"  ✓ Logged in as: {name} ({fy_id})")
            return True
        else:
            print(f"\n  ✗ Token invalid: {profile.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"\n  ✗ Verification failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════
# SETUP — First-time credential entry
# ═══════════════════════════════════════════════════════════

def cmd_setup():
    print(BANNER)
    print("  FIRST-TIME SETUP")
    print("  ─────────────────────────────────────")
    print("  You need an app from: https://myapi.fyers.in/dashboard/\n")

    creds = load_credentials()

    print("  [Required for both Manual & Auto mode]")
    client_id = input(f"  App ID (e.g. L9NY305RTW-100) [{creds.get('client_id', '')}]: ").strip()
    if client_id:
        creds['client_id'] = client_id

    secret_key = input(f"  Secret Key [{creds.get('secret_key', '****') if creds.get('secret_key') else ''}]: ").strip()
    if secret_key:
        creds['secret_key'] = secret_key

    redirect_uri = input(f"  Redirect URI [{creds.get('redirect_uri', 'https://trade.fyers.in/api-login/redirect-uri/index.html')}]: ").strip()
    if redirect_uri:
        creds['redirect_uri'] = redirect_uri
    elif not creds.get('redirect_uri'):
        creds['redirect_uri'] = 'https://trade.fyers.in/api-login/redirect-uri/index.html'

    print("\n  [Required ONLY for Auto mode (--auto)]")
    print("  (Press Enter to skip if you'll use Manual mode)\n")

    fyers_id = input(f"  Fyers Client ID (e.g. XS01234) [{creds.get('fyers_id', '')}]: ").strip()
    if fyers_id:
        creds['fyers_id'] = fyers_id

    pin = input(f"  4-digit PIN [{creds.get('pin', '****') if creds.get('pin') else ''}]: ").strip()
    if pin:
        creds['pin'] = pin

    totp_key = input(f"  TOTP Secret Key [{creds.get('totp_key', '****') if creds.get('totp_key') else ''}]: ").strip()
    if totp_key:
        creds['totp_key'] = totp_key

    print("\n  Where to find TOTP key:")
    print("  → Fyers App → Settings → Security → Two-Factor Authentication")
    print("  → When setting up, copy the 'Secret Key' (base32 string)")
    print("  → It looks like: JBSWY3DPEHPK3PXP\n")

    save_credentials(creds)

    # Validate required fields
    if not creds.get('client_id') or not creds.get('secret_key'):
        print("  ⚠ client_id and secret_key are required for any mode.")
        return

    print("  ─────────────────────────────────────")
    print("  Next steps:")
    print("    Manual mode:  python generate_token.py")
    print("    Auto mode:    python generate_token.py --auto")


# ═══════════════════════════════════════════════════════════
# MANUAL MODE — Browser-based login
# ═══════════════════════════════════════════════════════════

def cmd_manual():
    print(BANNER)
    print("  MODE: Manual (Browser Login)\n")

    # Check for existing valid token
    existing = load_token()
    if existing.get('access_token'):
        print(f"  ℹ Today's token already exists (generated at {existing.get('generated_at', '?')})")
        reuse = input("  Use existing token? (Y/n): ").strip().lower()
        if reuse != 'n':
            print(f"  ✓ Using existing token")
            verify_token(existing['client_id'], existing['access_token'])
            return

    creds = load_credentials()
    if not creds.get('client_id') or not creds.get('secret_key'):
        print("  ✗ No credentials found. Run: python generate_token.py --setup")
        return

    client_id    = creds['client_id']
    secret_key   = creds['secret_key']
    redirect_uri = creds.get('redirect_uri', 'https://trade.fyers.in/api-login/redirect-uri/index.html')

    # Step 1: Generate auth URL
    print("  Step 1: Generating login URL...")
    auth_session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        state="trading_engine",
    )

    auth_url = auth_session.generate_authcode()
    print(f"\n  Login URL:\n  {auth_url}\n")

    # Open browser
    try:
        webbrowser.open(auth_url)
        print("  ✓ Browser opened. Login to your Fyers account.")
    except Exception:
        print("  ⚠ Could not open browser. Copy the URL above and open manually.")

    # Step 2: User pastes the redirect URL or auth_code
    print("\n  Step 2: After login, you'll be redirected to a URL like:")
    print(f"  {redirect_uri}?auth_code=XXXXXX&state=trading_engine")
    print()

    user_input = input("  Paste the FULL redirect URL (or just the auth_code): ").strip()

    # Extract auth_code
    auth_code = ''
    if 'auth_code=' in user_input:
        parsed = urlparse(user_input)
        params = parse_qs(parsed.query)
        auth_code = params.get('auth_code', [''])[0]
        # If auth_code is in fragment
        if not auth_code:
            params = parse_qs(parsed.fragment)
            auth_code = params.get('auth_code', [''])[0]
    else:
        auth_code = user_input  # User pasted just the code

    if not auth_code:
        print("  ✗ Could not extract auth_code. Please try again.")
        return

    print(f"  ✓ Auth code: {auth_code[:20]}...")

    # Step 3: Exchange auth_code for access_token
    #         IMPORTANT: Need a NEW session with grant_type for token generation
    print("\n  Step 3: Exchanging for access token...")
    token_session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    token_session.set_token(auth_code)
    response = token_session.generate_token()

    if response.get('s') == 'ok' or response.get('access_token'):
        access_token = response['access_token']
        print(f"  ✓ Access token received!")
        save_token(access_token, client_id)
        verify_token(client_id, access_token)
        print_next_steps()
    else:
        print(f"  ✗ Token generation failed: {response}")
        print("  Common fixes:")
        print("    → Auth code expires quickly — try the flow again faster")
        print("    → Check that redirect_uri matches your app settings exactly")


# ═══════════════════════════════════════════════════════════
# AUTO MODE — TOTP + PIN (fully automated, no browser)
# ═══════════════════════════════════════════════════════════

def cmd_auto():
    print(BANNER)
    print("  MODE: Automated (TOTP + PIN)\n")

    # Check for existing valid token
    existing = load_token()
    if existing.get('access_token'):
        print(f"  ℹ Today's token exists (generated at {existing.get('generated_at', '?')})")
        reuse = input("  Use existing token? (Y/n): ").strip().lower()
        if reuse != 'n':
            verify_token(existing['client_id'], existing['access_token'])
            return

    creds = load_credentials()
    required = ['client_id', 'secret_key', 'fyers_id', 'pin', 'totp_key']
    missing = [k for k in required if not creds.get(k)]
    if missing:
        print(f"  ✗ Missing credentials: {', '.join(missing)}")
        print(f"  Run: python generate_token.py --setup")
        return

    try:
        import pyotp
        import requests
    except ImportError:
        print("  ✗ Required packages missing. Run:")
        print("    pip install pyotp requests")
        return

    client_id    = creds['client_id']
    secret_key   = creds['secret_key']
    redirect_uri = creds.get('redirect_uri', 'https://trade.fyers.in/api-login/redirect-uri/index.html')
    fyers_id     = creds['fyers_id']
    pin          = str(creds['pin'])
    totp_key     = creds['totp_key']

    def b64(s):
        return base64.b64encode(str(s).encode('ascii')).decode('ascii')

    try:
        ses = requests.Session()

        # Step 1: Send login OTP
        print("  Step 1: Sending login OTP...")
        r1 = ses.post(
            "https://api-t2.fyers.in/vagator/v2/send_login_otp_v2",
            json={"fy_id": b64(fyers_id), "app_id": "2"}
        )
        r1_data = r1.json()
        if r1.status_code != 200 or 'request_key' not in r1_data:
            print(f"  ✗ OTP send failed: {r1_data}")
            return
        print("  ✓ OTP request sent")

        # Step 2: Verify TOTP
        print("  Step 2: Generating & verifying TOTP...")
        totp = pyotp.TOTP(totp_key)
        otp = totp.now()

        r2 = ses.post(
            "https://api-t2.fyers.in/vagator/v2/verify_otp",
            json={"request_key": r1_data["request_key"], "otp": otp}
        )
        r2_data = r2.json()
        if r2.status_code != 200 or 'request_key' not in r2_data:
            print(f"  ✗ OTP verification failed: {r2_data}")
            print("  Possible cause: TOTP key is incorrect or time is out of sync")
            return
        print("  ✓ TOTP verified")

        # Step 3: Verify PIN (using same session for cookies)
        print("  Step 3: Verifying PIN...")
        r3 = ses.post(
            "https://api-t2.fyers.in/vagator/v2/verify_pin_v2",
            json={
                "request_key": r2_data["request_key"],
                "identity_type": "pin",
                "identifier": b64(pin),
            }
        )
        r3_data = r3.json()
        if r3.status_code != 200 or 'data' not in r3_data:
            print(f"  ✗ PIN verification failed: {r3_data}")
            return
        print("  ✓ PIN verified")

        # Step 4: Get auth_code (MUST use same session with bearer token)
        print("  Step 4: Generating auth code...")
        ses.headers.update({
            "Authorization": f"Bearer {r3_data['data']['access_token']}"
        })

        r4 = ses.post(
            "https://api-t1.fyers.in/api/v3/token",
            json={
                "fyers_id":      fyers_id,
                "app_id":        client_id.split('-')[0],
                "redirect_uri":  redirect_uri,
                "appType":       "100",
                "code_challenge": "",
                "state":         "None",
                "scope":         "",
                "nonce":         "",
                "response_type": "code",
                "create_cookie": True,
            }
        )
        r4_data = r4.json()

        # Extract auth_code from response
        auth_code = ''

        # Format 1: Url field with auth_code in query params
        token_url = r4_data.get('Url') or r4_data.get('url', '')
        if token_url:
            parsed = urlparse(token_url)
            auth_code = parse_qs(parsed.query).get('auth_code', [''])[0]

        # Format 2: code field at top level
        if not auth_code and r4_data.get('code') and isinstance(r4_data['code'], str) and len(r4_data['code']) > 10:
            auth_code = r4_data['code']

        if not auth_code:
            print(f"  ✗ Could not extract auth_code")
            print(f"  Response: {json.dumps(r4_data, indent=2)[:500]}")
            return

        print(f"  ✓ Auth code obtained")

        # Step 5: Final token exchange
        print("  Step 5: Exchanging for final access token...")
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key,
            redirect_uri=redirect_uri,
            response_type="code",
            grant_type="authorization_code",
        )
        session.set_token(auth_code)
        response = session.generate_token()

        print(f"  ✓ Auth code obtained")

        # Step 5: Final token exchange
        print("  Step 5: Exchanging for final access token...")
        session.set_token(auth_code)
        response = session.generate_token()

        if response.get('access_token'):
            access_token = response['access_token']
            print(f"  ✓ Access token generated!")
            save_token(access_token, client_id)
            verify_token(client_id, access_token)
            print_next_steps()
        else:
            print(f"  ✗ Final token exchange failed: {response}")

    except Exception as e:
        print(f"\n  ✗ Error during auto-login: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════
# CHECK — Quick token status check
# ═══════════════════════════════════════════════════════════

def cmd_check():
    print(BANNER)
    existing = load_token()
    if not existing.get('access_token'):
        print("  ✗ No token found for today.")
        print("  Run: python generate_token.py")
        return

    print(f"  Token date:      {existing.get('date')}")
    print(f"  Generated at:    {existing.get('generated_at')}")
    print(f"  Client ID:       {existing.get('client_id')}")
    verify_token(existing['client_id'], existing['access_token'])


def print_next_steps():
    print("\n  ─────────────────────────────────────")
    print("  NEXT STEPS:")
    print("    python fetch_data.py --download    # Download market data")
    print("    python app.py                      # Start trading dashboard")
    print("    http://localhost:5000               # Open in browser")
    print()


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fyers Access Token Generator')
    parser.add_argument('--setup', action='store_true', help='First-time credential setup')
    parser.add_argument('--auto',  action='store_true', help='Automated login using TOTP + PIN')
    parser.add_argument('--check', action='store_true', help='Check if today\'s token is valid')

    args = parser.parse_args()

    if args.setup:
        cmd_setup()
    elif args.auto:
        cmd_auto()
    elif args.check:
        cmd_check()
    else:
        cmd_manual()