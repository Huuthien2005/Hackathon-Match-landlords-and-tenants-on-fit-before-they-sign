"""Accounts and sign-in, stored in data/deservia.db (tables `users` and `sessions`).

- Passwords: PBKDF2-SHA256, 200,000 iterations, random salt per user. Plain passwords are never stored.
- Sessions: random 32-byte tokens, sent as "Authorization: Bearer <token>", expire after 7 days.
- Roles: tenant and landlord sign themselves up. The agent (website owner) account cannot be
  created through sign-up; it is seeded on first start (see seed_accounts).
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
import threading
import time
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "deservia.db"
SESSION_DAYS = 7
ITER = 200_000
_lock = threading.Lock()
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    pw TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('tenant', 'landlord', 'agent')),
    answers TEXT,
    plan TEXT NOT NULL DEFAULT 'free',
    consent_at REAL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires REAL NOT NULL
);
"""


class AuthError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


@contextmanager
def _con():
    """Open, commit on success, and ALWAYS close (an open connection can lock the file on Windows)."""
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    try:
        con.executescript(SCHEMA)
        cols = [r[1] for r in con.execute("PRAGMA table_info(users)")]            # older databases
        if "plan" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        if "consent_at" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN consent_at REAL")
        yield con
        con.commit()
    finally:
        con.close()


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2${ITER}${salt.hex()}${h.hex()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(got.hex(), h)
    except (ValueError, TypeError):
        return False


def pool_id(user):
    """The id this user has in the matching pool."""
    return f'u_{user["id"]}' if user["role"] == "tenant" else f'ul_{user["id"]}'


def _row(r):
    if not r:
        return None
    u = {"id": r[0], "email": r[1], "role": r[2], "answers": json.loads(r[3]) if r[3] else None,
         "plan": (r[4] if len(r) > 4 else None) or "free"}
    u["pool_id"] = pool_id(u) if u["role"] != "agent" else None
    return u


def signup(email, password, role, _allow_agent=False, consent=False):
    email = (email or "").strip().lower()
    if not EMAIL.match(email):
        raise AuthError(400, "Enter a valid email address")
    if len(password or "") < 8:
        raise AuthError(400, "Password must be at least 8 characters")
    if role not in ("tenant", "landlord") and not (_allow_agent and role == "agent"):
        raise AuthError(400, "Choose tenant or landlord")
    with _lock, _con() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise AuthError(409, "An account with this email already exists")
        now = time.time()
        cur = con.execute("INSERT INTO users (email, pw, role, consent_at, created_at) VALUES (?,?,?,?,?)",
                          (email, hash_password(password), role, now if consent else None, now))
        return cur.lastrowid


MAX_FAILS, FAIL_WINDOW = 8, 600       # 8 wrong passwords per email per 10 minutes
_fails = {}


def _too_many(email):
    now = time.time()
    with _lock:
        recent = [t for t in _fails.get(email, []) if now - t < FAIL_WINDOW]
        _fails[email] = recent
        return len(recent) >= MAX_FAILS


def _record_fail(email):
    with _lock:
        _fails.setdefault(email, []).append(time.time())


def signin(email, password):
    email = (email or "").strip().lower()
    if _too_many(email):
        raise AuthError(429, "Too many sign-in attempts. Please wait a few minutes and try again.")
    with _con() as con:
        r = con.execute("SELECT id, pw FROM users WHERE email=?", (email,)).fetchone()
        if not r or not check_password(password or "", r[1]):
            _record_fail(email)
            raise AuthError(401, "Wrong email or password")
        _fails.pop(email, None)
        token = secrets.token_urlsafe(32)
        con.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        con.execute("INSERT INTO sessions VALUES (?,?,?)", (token, r[0], time.time() + SESSION_DAYS * 86400))
    return token


def signout(token):
    with _con() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))


def user_from_token(token):
    if not token:
        return None
    with _con() as con:
        r = con.execute("SELECT u.id, u.email, u.role, u.answers, u.plan FROM sessions s JOIN users u ON u.id = s.user_id "
                        "WHERE s.token=? AND s.expires > ?", (token, time.time())).fetchone()
    return _row(r)


def save_answers(user_id, answers):
    with _lock, _con() as con:
        con.execute("UPDATE users SET answers=? WHERE id=?", (json.dumps(answers), user_id))


def verify_password(user_id, password):
    with _con() as con:
        r = con.execute("SELECT pw FROM users WHERE id=?", (user_id,)).fetchone()
    return bool(r) and check_password(password or "", r[0])


def delete_user(user_id):
    """PIPEDA: delete the account, its answers and every session. Swipes are removed by the caller."""
    with _lock, _con() as con:
        con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM users WHERE id=?", (user_id,))


def set_plan(user_id, plan):
    with _lock, _con() as con:
        con.execute("UPDATE users SET plan=? WHERE id=?", (plan, user_id))


def get_user(user_id):
    with _con() as con:
        return _row(con.execute("SELECT id, email, role, answers, plan FROM users WHERE id=?", (user_id,)).fetchone())


def list_users():
    with _con() as con:
        rows = con.execute("SELECT id, email, role, answers, plan, created_at FROM users ORDER BY id").fetchall()
    out = []
    for r in rows:
        u = _row(r[:5])
        u["created_at"] = r[5]
        out.append(u)
    return out


def reset_accounts():
    """Public demo: start from a clean slate (no leftover test accounts, sessions or swipes)."""
    with _lock, _con() as con:
        con.execute("DELETE FROM sessions")
        con.execute("DELETE FROM users")
        try:
            con.execute("DELETE FROM feedback")
        except sqlite3.OperationalError:
            pass


def owner_password_is_default():
    return not os.environ.get("DESERVIA_ADMIN_PASSWORD")


def seed_accounts():
    """First start: an agent (owner) account plus one demo tenant and one demo landlord with
    finished questionnaires, so the demo works immediately. Change these passwords before real use."""
    from .data import DEMO_LISTINGS, DEMO_TENANTS
    created = []
    admin_pw = os.environ.get("DESERVIA_ADMIN_PASSWORD", "admin1234")
    accounts = [("owner@deservia.ca", admin_pw, "agent", None),
                ("alex@demo.ca", "demo1234", "tenant", _tenant_answers(DEMO_TENANTS[0])),
                ("maple@demo.ca", "demo1234", "landlord", _landlord_answers(DEMO_LISTINGS[0])),
                # fresh free accounts for testing "10 free matches, then subscribe"
                ("sam@demo.ca", "demo1234", "tenant", _tenant_answers(DEMO_TENANTS[1])),
                ("sandalwood@demo.ca", "demo1234", "landlord", _landlord_answers(DEMO_LISTINGS[1]))]
    for email, pw, role, answers in accounts:
        try:
            uid = signup(email, pw, role, _allow_agent=True)
        except AuthError:
            if role == "agent" and not owner_password_is_default():
                with _lock, _con() as con:            # always enforce the secret owner password
                    con.execute("UPDATE users SET pw=? WHERE email=?", (hash_password(pw), email))
            continue                      # already exists
        if answers:
            save_answers(uid, answers)
        created.append(email)
    return created


def _tenant_answers(t):
    keys = ["rental_type", "area", "budget", "bedrooms_needed", "hobbies", "pets", "pet_kind", "smoking", "chronotype",
            "social", "tidy", "music", "travel", "cooking_smells", "drive", "repair_speed", "timing", "ideal_text"]
    a = {k: t[k] for k in keys if k in t}
    if t.get("pets") == "have_pet":
        a["service_animal"] = "yes" if t.get("service_animal") else "no"
    return a


def _landlord_answers(l):
    a = {k: l[k] for k in ("rental_type", "area", "title", "rent", "bedrooms", "parking", "kitchen", "entrance",
                           "pet_policy", "smoke_policy", "timing", "description")}
    a["landlord_on_site"] = "yes" if l.get("landlord_on_site") else "no"
    ll = l["landlord"]
    a.update({k: ll[k] for k in ("hobbies", "pets", "smoking", "chronotype", "social", "tidy", "music", "travel",
                                 "cooking_smells", "repair_speed", "ideal_text") if k in ll})
    return a
