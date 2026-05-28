"""
database.py — SQLite persistence layer
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'trading_engine.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables on first run."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_name  TEXT    NOT NULL,
                date        TEXT    DEFAULT (date('now')),
                capital     REAL    NOT NULL DEFAULT 25000,
                risk        REAL    NOT NULL DEFAULT 500,
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS candles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                type        TEXT    NOT NULL,
                datetime    TEXT,
                open        REAL    NOT NULL,
                high        REAL    NOT NULL,
                low         REAL    NOT NULL,
                close       REAL    NOT NULL,
                volume      INTEGER DEFAULT 0,
                idx         INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_candles_session ON candles(session_id, type);

            CREATE TABLE IF NOT EXISTS signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                time        TEXT,
                type        TEXT    NOT NULL CHECK(type IN ('BUY','SELL')),
                entry       REAL,
                sl          REAL,
                t1          REAL,
                t2          REAL,
                t3          REAL,
                qty         INTEGER,
                cap_needed  REAL,
                risk_amt    REAL,
                pot_pnl     REAL,
                rr          REAL,
                score       INTEGER,
                grade       TEXT DEFAULT '?',
                reasons     TEXT,  -- JSON array
                candle_index INTEGER,
                vwap        REAL,
                ema9        REAL,
                ema21       REAL,
                atr         REAL,
                metadata    TEXT  -- JSON: V2 extra data
            );

            CREATE INDEX IF NOT EXISTS idx_signals_session ON signals(session_id);

            CREATE TABLE IF NOT EXISTS journal (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
                signal_id   INTEGER REFERENCES signals(id)  ON DELETE SET NULL,
                stock_name  TEXT,
                trade_date  TEXT    DEFAULT (date('now')),
                type        TEXT    CHECK(type IN ('BUY','SELL')),
                entry       REAL,
                exit_price  REAL,
                qty         INTEGER,
                sl          REAL,
                target      REAL,
                outcome     TEXT    CHECK(outcome IN ('WIN','LOSS','PARTIAL','MISSED','BE')),
                pnl         REAL,
                charges     REAL    DEFAULT 0,
                net_pnl     REAL,
                notes       TEXT,
                created_at  TEXT    DEFAULT (datetime('now'))
            );
        """)
    print(f"  DB ready: {DB_PATH}")


# ─── Sessions ─────────────────────────────────────────────────────────────────

def create_session(stock_name, capital, risk):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (stock_name, capital, risk) VALUES (?,?,?)",
            (stock_name, capital, risk)
        )
        return cur.lastrowid


def get_session(session_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None


def get_sessions():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.*, COUNT(DISTINCT c.id) as candle_count, COUNT(DISTINCT sg.id) as signal_count "
            "FROM sessions s "
            "LEFT JOIN candles c  ON c.session_id=s.id AND c.type='cash' "
            "LEFT JOIN signals sg ON sg.session_id=s.id "
            "GROUP BY s.id ORDER BY s.id DESC LIMIT 50"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Candles ──────────────────────────────────────────────────────────────────

def store_candles(session_id, candles, ctype):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO candles (session_id, type, datetime, open, high, low, close, volume, idx) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(session_id, ctype, c.get('datetime'), c['open'], c['high'],
              c['low'], c['close'], c.get('volume', 0), i)
             for i, c in enumerate(candles)]
        )


def get_candles(session_id, ctype='cash'):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM candles WHERE session_id=? AND type=? ORDER BY idx",
            (session_id, ctype)
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Signals ──────────────────────────────────────────────────────────────────

def store_signals(session_id, sigs):
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO signals
               (session_id,time,type,entry,sl,t1,t2,t3,qty,cap_needed,risk_amt,
                pot_pnl,rr,score,grade,reasons,candle_index,vwap,ema9,ema21,atr,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(session_id, s['time'], s['type'], s['entry'], s['sl'],
              s['t1'], s['t2'], s['t3'], s['qty'], s['cap_needed'],
              s['risk_amt'], s['pot_pnl'], s['rr'], s['score'],
              s.get('grade', '?'),
              json.dumps(s['reasons']), s['candle_index'],
              s.get('vwap'), s.get('ema9'), s.get('ema21'), s.get('atr'),
              json.dumps({k: s[k] for k in (
                  'conviction', 'htf_5m', 'htf_15m', 'regime', 'regime_conf',
                  'momentum', 'vol_delta', 'vol_ratio', 'time_window',
                  'patterns', 'sr_level', 'rs_vs_index', 'gap', 'size_pct',
              ) if k in s}))
             for s in sigs]
        )


def clear_signals(session_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM signals WHERE session_id=?", (session_id,))


def get_signals(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE session_id=? ORDER BY candle_index",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['reasons'] = json.loads(d['reasons']) if d['reasons'] else []
            try:
                d['metadata'] = json.loads(d['metadata']) if d.get('metadata') else {}
            except (json.JSONDecodeError, TypeError):
                d['metadata'] = {}
            # Merge metadata into top-level for frontend convenience
            d.update(d.pop('metadata', {}))
            result.append(d)
        return result


# ─── Journal ──────────────────────────────────────────────────────────────────

def add_journal_entry(data):
    pnl = None
    if data.get('exit_price') and data.get('entry') and data.get('qty'):
        direction = 1 if data.get('type') == 'BUY' else -1
        pnl = (float(data['exit_price']) - float(data['entry'])) * int(data['qty']) * direction
        pnl = round(pnl, 2)

    charges = round(pnl * 0.001, 2) if pnl else 0  # ~0.1% estimate
    net_pnl = round(pnl - charges, 2) if pnl else None

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO journal
               (session_id,signal_id,stock_name,trade_date,type,entry,exit_price,
                qty,sl,target,outcome,pnl,charges,net_pnl,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get('session_id'), data.get('signal_id'),
             data.get('stock_name'), data.get('trade_date', datetime.now().strftime('%Y-%m-%d')),
             data.get('type'), data.get('entry'), data.get('exit_price'),
             data.get('qty'), data.get('sl'), data.get('target'),
             data.get('outcome'), pnl, charges, net_pnl, data.get('notes'))
        )
        return cur.lastrowid


def get_journal(session_id=None):
    with get_conn() as conn:
        if session_id:
            rows = conn.execute(
                "SELECT * FROM journal WHERE session_id=? ORDER BY created_at DESC",
                (session_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM journal ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
        return [dict(r) for r in rows]


def delete_journal_entry(entry_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM journal WHERE id=?", (entry_id,))
