import json, os

f = 'fyers_config.json'
c = json.load(open(f)) if os.path.exists(f) else {}

c['watchlist'] = [
    'NSE:COALINDIA-EQ',
    'NSE:ONGC-EQ',
    'NSE:IRCTC-EQ',
    'NSE:TATASTEEL-EQ',
    'NSE:HDFCBANK-EQ',
    'NSE:HINDZINC-EQ',
    'NSE:KOTAKBANK-EQ',
    'NSE:VBL-EQ',
    'NSE:LICI-EQ',
    'NSE:NATIONALUM-EQ',
    'NSE:PFC-EQ',
    'NSE:INDUSTOWER-EQ',
    'NSE:TATAPOWER-EQ',
    'NSE:MARICO-EQ',
    'NSE:NESTLEIND-EQ',
    'NSE:BSE-EQ',
    'NSE:NIPPONLIFE-EQ',
    'NSE:HDFCAMC-EQ',
    'NSE:MCX-EQ',
    'NSE:ETERNAL-EQ',
    'NSE:SBIN-EQ',
    'NSE:COFORGE-EQ',
    'NSE:PERSISTENT-EQ',
    'NSE:TORNTPHARM-EQ',
    'NSE:CUMMINSIND-EQ',
]

c['index_symbol'] = 'NSE:NIFTY50-INDEX'
c['capital'] = 25000
c['risk_per_trade'] = 500

json.dump(c, open(f, 'w'), indent=2)
print(f'Done - {len(c["watchlist"])} stocks configured')