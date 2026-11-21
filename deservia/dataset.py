"""Read and write the Deservia dataset as CSV files or a SQLite database.

Tables (same columns in both formats):
  tenants.csv    one row per tenant: questionnaire answers (lists joined with "|")
  listings.csv   one row per listing: listing form fields + the landlord's answers (ll_ prefix)
  tenancies.csv  one row per past placement: tenant_id, listing_id, start_date,
                 outcome (1 = smooth first 12 months, 0 = dispute) and dispute_reason

All rows are made up. `hidden_group` exists ONLY for the fairness audit; the scorer's allowlist
never lets it through, and the model's features never include it.
"""
import csv
import sqlite3
from pathlib import Path

TENANT_COLS = ["id", "rental_type", "area", "budget", "bedrooms_needed", "hobbies", "work", "days",
               "pets", "pet_kind", "service_animal", "smoking", "diet", "chronotype", "social", "tidy",
               "music", "travel", "drive", "timing", "cooking_smells", "repair_speed", "ideal_text",
               "hidden_group"]
LL_FIELDS = ["pets", "smoking", "chronotype", "social", "tidy", "music", "travel", "hobbies",
             "cooking_smells", "repair_speed", "ideal_text", "diet", "work", "days", "hidden_group"]
LISTING_COLS = ["id", "title", "area", "rental_type", "rent", "bedrooms", "parking", "kitchen", "entrance",
                "pet_policy", "smoke_policy", "timing", "landlord_on_site", "description"] + \
               [f"ll_{f}" for f in LL_FIELDS]
TENANCY_COLS = ["tenant_id", "listing_id", "start_date", "outcome", "dispute_reason"]

INTS = {"budget", "bedrooms_needed", "rent", "bedrooms", "outcome"}
BOOLS = {"service_animal", "landlord_on_site"}
LISTS = {"hobbies", "ll_hobbies"}


# ---------------------------------------------------------------- dict <-> row
def _cell(k, v):
    if k in LISTS:
        return "|".join(v or [])
    if k in BOOLS:
        return int(bool(v))
    return "" if v is None else v


def _parse(k, v):
    if v is None or v == "":
        return [] if k in LISTS else None
    if k in LISTS:
        return str(v).split("|")
    if k in BOOLS:
        return str(v) in ("1", "True", "true")
    if k in INTS:
        return int(float(v))
    return v


def tenant_to_row(t: dict) -> dict:
    t = {**t, "hidden_group": t.get("hidden_group", t.get("group"))}
    return {c: _cell(c, t.get(c)) for c in TENANT_COLS}


def row_to_tenant(r: dict) -> dict:
    t = {c: _parse(c, r.get(c)) for c in TENANT_COLS}
    t["role"] = "tenant"
    t["group"] = t.pop("hidden_group")          # audit only
    return {k: v for k, v in t.items() if v is not None}


def listing_to_row(l: dict) -> dict:
    flat = {**l, **{f"ll_{f}": l["landlord"].get(f if f != "hidden_group" else "group") for f in LL_FIELDS}}
    return {c: _cell(c, flat.get(c)) for c in LISTING_COLS}


def row_to_listing(r: dict) -> dict:
    d = {c: _parse(c, r.get(c)) for c in LISTING_COLS}
    ll = {f: d.pop(f"ll_{f}") for f in LL_FIELDS}
    ll["group"] = ll.pop("hidden_group")
    ll["role"] = "landlord"
    d["landlord"] = {k: v for k, v in ll.items() if v is not None}
    d["description"] = d.get("description") or ""
    return d


def row_to_tenancy(r: dict) -> dict:
    return {c: _parse(c, r.get(c)) for c in TENANCY_COLS}


# ---------------------------------------------------------------- writers
def write_csv(folder, tenants, listings, tenancies):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    for name, cols, rows in (("tenants", TENANT_COLS, map(tenant_to_row, tenants)),
                             ("listings", LISTING_COLS, map(listing_to_row, listings)),
                             ("tenancies", TENANCY_COLS, tenancies)):
        with open(folder / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


def write_sqlite(path, tenants, listings, tenancies):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    for name, cols, rows, key in (("tenants", TENANT_COLS, list(map(tenant_to_row, tenants)), "id"),
                                  ("listings", LISTING_COLS, list(map(listing_to_row, listings)), "id"),
                                  ("tenancies", TENANCY_COLS, tenancies, None)):
        defs = ", ".join(f'"{c}" {"INTEGER" if c in INTS | BOOLS else "TEXT"}'
                         + (" PRIMARY KEY" if c == key else "") for c in cols)
        con.execute(f"CREATE TABLE {name} ({defs})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})",
                        [[r[c] for c in cols] for r in rows])
    con.execute("CREATE INDEX idx_tenancy_tenant ON tenancies(tenant_id)")
    con.commit()
    con.close()


# ---------------------------------------------------------------- reader
def load(source="data/deservia.db"):
    """Load (tenants, listings, tenancies) from a .db file or a folder of CSVs.
    Returns lists of dicts in the engine's format."""
    source = Path(source)
    if source.suffix == ".db":
        con = sqlite3.connect(source)
        con.row_factory = sqlite3.Row
        fetch = lambda t: [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
        raw = fetch("tenants"), fetch("listings"), fetch("tenancies")
        con.close()
    else:
        def fetch(t):
            with open(source / f"{t}.csv", newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        raw = fetch("tenants"), fetch("listings"), fetch("tenancies")
    return ([row_to_tenant(r) for r in raw[0]], [row_to_listing(r) for r in raw[1]],
            [row_to_tenancy(r) for r in raw[2]])
