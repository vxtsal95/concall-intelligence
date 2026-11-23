import sqlite3, json
from datetime import datetime, timezone
from .config import DB_PATH

SCHEMA = '''
CREATE TABLE IF NOT EXISTS filings (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 dedupe_key TEXT UNIQUE NOT NULL,
 company TEXT, symbol TEXT, scrip_code TEXT, exchange TEXT NOT NULL,
 filing_date TEXT, quarter TEXT, title TEXT, source_url TEXT NOT NULL,
 pdf_path TEXT, status TEXT NOT NULL DEFAULT 'discovered', error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
 filing_id INTEGER PRIMARY KEY REFERENCES filings(id) ON DELETE CASCADE,
 payload TEXT NOT NULL, markdown TEXT NOT NULL, created_at TEXT NOT NULL
);
'''

def connect():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    with connect() as c: c.executescript(SCHEMA)

def add_filing(item):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        cur = c.execute('''INSERT OR IGNORE INTO filings
        (dedupe_key,company,symbol,scrip_code,exchange,filing_date,quarter,title,source_url,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,'discovered',?,?)''',
        (item['dedupe_key'], item.get('company'), item.get('symbol'), item.get('scrip_code'), item['exchange'], item.get('filing_date'), item.get('quarter'), item.get('title'), item['source_url'], now, now))
        return cur.rowcount == 1

def update_filing(filing_id, **fields):
    if not fields: return
    fields['updated_at'] = datetime.now(timezone.utc).isoformat()
    keys = list(fields)
    with connect() as c:
        c.execute('UPDATE filings SET ' + ','.join(f'{k}=?' for k in keys) + ' WHERE id=?', [fields[k] for k in keys] + [filing_id])

def get_filing(filing_id):
    with connect() as c: return c.execute('SELECT * FROM filings WHERE id=?', (filing_id,)).fetchone()

def save_summary(filing_id, payload, markdown):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO summaries VALUES(?,?,?,?)', (filing_id, json.dumps(payload, ensure_ascii=False), markdown, now))
        c.execute("UPDATE filings SET status='processed', updated_at=? WHERE id=?", (now, filing_id))

def list_filings():
    with connect() as c:
        rows = c.execute('''SELECT f.*, s.payload, s.markdown FROM filings f LEFT JOIN summaries s ON f.id=s.filing_id ORDER BY COALESCE(f.filing_date,f.created_at) DESC LIMIT 200''').fetchall()
        return [dict(r) for r in rows]

def known_keys():
    with connect() as c: return {r[0] for r in c.execute('SELECT dedupe_key FROM filings')}
