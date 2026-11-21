"""Swipe feedback (♥ like / ✕ pass), stored in the `feedback` table of data/deservia.db.

Each row keeps the pair's feature vector at swipe time, so retraining never has to re-score.
A like is a PREFERENCE signal, not an outcome: it tells us what this person wants to see,
not whether the tenancy will go well. The retrain gives likes a modest weight next to the
65,000 tenancy outcomes, and the personal model (ml/personal.py) uses them per user.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "deservia.db"
_lock = threading.Lock()

SCHEMA = """CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,          -- tenant id (tenant swiping homes) or listing id (landlord swiping tenants)
    role TEXT NOT NULL,             -- 'tenant' or 'landlord'
    tenant_id TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    liked INTEGER NOT NULL,         -- 1 = ♥, 0 = ✕
    match_pct INTEGER,
    ml_success_pct INTEGER,
    features TEXT NOT NULL,         -- JSON list, same order as ml.features.FEATURES
    created_at REAL NOT NULL
)"""


def _con():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    con.execute("CREATE INDEX IF NOT EXISTS idx_fb_user ON feedback(user_id)")
    return con


def add(user_id, role, tenant_id, listing_id, liked, features, match_pct=None, ml_pct=None):
    with _lock, _con() as con:
        # one vote per user per item: a re-swipe replaces the old vote
        con.execute("DELETE FROM feedback WHERE user_id=? AND tenant_id=? AND listing_id=?",
                    (user_id, tenant_id, listing_id))
        con.execute("INSERT INTO feedback (user_id, role, tenant_id, listing_id, liked, match_pct, "
                    "ml_success_pct, features, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (user_id, role, tenant_id, listing_id, int(bool(liked)), match_pct, ml_pct,
                     json.dumps([None if f != f else f for f in features]), time.time()))


def swiped_ids(user_id, role):
    """Items this user already swiped, so the next deck shows new ones."""
    col = "listing_id" if role == "tenant" else "tenant_id"
    with _con() as con:
        return {r[0] for r in con.execute(f"SELECT {col} FROM feedback WHERE user_id=?", (user_id,))}


def rows(user_id=None):
    """(features, liked) for one user or everyone. NaN restored from JSON null."""
    q, args = "SELECT features, liked FROM feedback", ()
    if user_id:
        q, args = q + " WHERE user_id=?", (user_id,)
    with _con() as con:
        out = [(json.loads(f), l) for f, l in con.execute(q, args)]
    return [[float("nan") if v is None else v for v in f] for f, _ in out], [l for _, l in out]


def counts(user_id=None):
    q, args = "SELECT COUNT(*), COALESCE(SUM(liked),0) FROM feedback", ()
    if user_id:
        q, args = q + " WHERE user_id=?", (user_id,)
    with _con() as con:
        n, likes = con.execute(q, args).fetchone()
    return {"swipes": n, "likes": likes, "passes": n - likes}


def reset(user_id=None):
    with _lock, _con() as con:
        if user_id:
            con.execute("DELETE FROM feedback WHERE user_id=?", (user_id,))
        else:
            con.execute("DELETE FROM feedback")
