#!/usr/bin/env python3
"""
setup.py — One-command project setup
======================================
Run:  python setup.py
Does:
  1. Creates .venv virtual environment
  2. Installs all dependencies
  3. Initializes the SQLite database
  4. Verifies all modules import correctly
  5. Prints next steps
"""

import subprocess
import sys
import os
import platform

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = platform.system() == 'Windows'

VENV_DIR = os.path.join(PROJECT_DIR, '.venv')
PYTHON = os.path.join(VENV_DIR, 'Scripts' if IS_WINDOWS else 'bin', 'python')
PIP    = os.path.join(VENV_DIR, 'Scripts' if IS_WINDOWS else 'bin', 'pip')
ACTIVATE = os.path.join(VENV_DIR, 'Scripts' if IS_WINDOWS else 'bin',
                        'activate.bat' if IS_WINDOWS else 'activate')

BANNER = """
  ⚡ Trade Signal Engine — Setup
  ═══════════════════════════════════
"""


def run(cmd, desc=''):
    if desc:
        print(f'  → {desc}')
    result = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if result.returncode != 0:
        print(f'    ✗ FAILED: {result.stderr.strip()[:200]}')
        return False
    return True


def main():
    print(BANNER)
    print(f'  Python:  {sys.version.split()[0]}')
    print(f'  OS:      {platform.system()} {platform.machine()}')
    print(f'  Project: {PROJECT_DIR}')
    print()

    # ── Step 1: Create venv ──
    if os.path.exists(VENV_DIR):
        print(f'  ✓ .venv already exists')
    else:
        print(f'  [1/5] Creating virtual environment...')
        if not run([sys.executable, '-m', 'venv', VENV_DIR], 'python -m venv .venv'):
            print('\n  ⚠ Failed to create venv. Make sure python3-venv is installed:')
            print('    sudo apt install python3.11-venv  (Ubuntu/Debian)')
            return

    # Verify venv python exists
    if not os.path.exists(PYTHON):
        print(f'  ✗ Could not find venv python at {PYTHON}')
        return
    print(f'  ✓ .venv ready at {VENV_DIR}')
    print()

    # ── Step 2: Upgrade pip ──
    print(f'  [2/5] Upgrading pip...')
    run([PYTHON, '-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'], 'pip install --upgrade pip')

    # ── Step 3: Install dependencies ──
    print(f'  [3/5] Installing dependencies...')
    req_file = os.path.join(PROJECT_DIR, 'requirements.txt')

    if not run([PIP, 'install', '-r', req_file, '--quiet'], f'pip install -r requirements.txt'):
        # Try without fyers (it may fail on some systems)
        print('    Retrying core dependencies only...')
        run([PIP, 'install', 'flask>=3.0.0', 'flask-cors>=4.0.0', '--quiet'], 'pip install flask flask-cors')
        print('    ⚠ fyers-apiv3 may need manual install:')
        print(f'      {PIP} install fyers-apiv3')

    # Show installed packages
    result = subprocess.run([PIP, 'list', '--format=columns'], capture_output=True, text=True)
    installed = result.stdout.strip().split('\n')[2:]  # skip header
    key_packages = ['flask', 'fyers', 'werkzeug']
    print('  Installed:')
    for line in installed:
        name = line.split()[0].lower() if line.strip() else ''
        if any(k in name for k in key_packages):
            print(f'    ✓ {line.strip()}')
    print()

    # ── Step 4: Initialize database ──
    print(f'  [4/5] Initializing database...')
    init_result = subprocess.run(
        [PYTHON, '-c', 'import database as db; db.init_db()'],
        cwd=PROJECT_DIR, capture_output=True, text=True
    )
    if init_result.returncode == 0:
        print(f'  ✓ Database initialized')
    else:
        print(f'  ✗ DB init failed: {init_result.stderr[:200]}')
    print()

    # ── Step 5: Verify all modules ──
    print(f'  [5/5] Verifying modules...')
    verify_code = """
import sys
sys.path.insert(0, '.')
modules_ok = True
checks = [
    ('database',             'import database'),
    ('strategies',           'from engine.strategies import compute_all'),
    ('signals V2',           'from engine.signals_v2 import generate_signals_v2'),
    ('advanced indicators',  'from engine.advanced import detect_patterns'),
    ('filters',              'from engine.filters import get_time_multiplier'),
    ('backtester',           'from engine.backtester import backtest_session_replay'),
    ('fyers client',         'from fyers_client import FyersClient'),
    ('flask app',            'from app import app'),
]
for name, code in checks:
    try:
        exec(code)
        print(f'    ✓ {name}')
    except Exception as e:
        print(f'    ✗ {name}: {e}')
        modules_ok = False
print()
if modules_ok:
    print('  ══════════════════════════════════════')
    print('  ✓ ALL MODULES VERIFIED — SETUP COMPLETE')
    print('  ══════════════════════════════════════')
else:
    print('  ⚠ Some modules had issues (see above)')
"""
    subprocess.run([PYTHON, '-c', verify_code], cwd=PROJECT_DIR)

    # ── Next steps ──
    print()
    print('  NEXT STEPS:')
    print('  ─────────────────────────────────────')
    if IS_WINDOWS:
        print(f'  1. Activate venv:   .venv\\Scripts\\activate')
        print(f'  2. Configure Fyers: python fetch_data.py --setup')
        print(f'  3. Download data:   python fetch_data.py --download')
        print(f'  4. Start server:    python app.py')
        print(f'  5. Open browser:    http://localhost:5000')
    else:
        print(f'  1. Activate venv:   source .venv/bin/activate')
        print(f'  2. Configure Fyers: python fetch_data.py --setup')
        print(f'  3. Download data:   python fetch_data.py --download')
        print(f'  4. Start server:    python app.py')
        print(f'  5. Open browser:    http://localhost:5000')
    print()
    print(f'  Or run everything without activating venv:')
    if IS_WINDOWS:
        print(f'    .venv\\Scripts\\python app.py')
    else:
        print(f'    .venv/bin/python app.py')
    print()


if __name__ == '__main__':
    main()
