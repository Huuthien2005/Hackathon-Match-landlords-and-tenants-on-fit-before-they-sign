"""Generate the made-up Deservia dataset and save it as CSV files AND a SQLite database.

    python generate_dataset.py                       # 5,000 tenants, 1,000 listings (default)
    python generate_dataset.py --tenants 20000 --listings 3000 --per-tenant 20

For every tenant we sample candidate listings, keep those that pass the hard filters (a real
placement could only happen there), and record up to --per-tenant past tenancies with a
simulated outcome and dispute reason. Output in data/: tenants.csv, listings.csv,
tenancies.csv and deservia.db. No real person's data.
"""
import argparse
import random
from collections import Counter
from datetime import date, timedelta

from deservia.data import generate
from deservia.dataset import write_csv, write_sqlite
from deservia.engine import score_pair
from deservia.ml.simulate import simulate_outcome


def build(n_tenants, n_listings, per_tenant, seed):
    tenants, listings = generate(n_tenants, n_listings, seed=seed)
    rng = random.Random(seed + 1)
    start = date(2023, 1, 1)
    tenancies = []
    for i, t in enumerate(tenants, 1):
        kept = 0
        for l in rng.sample(listings, min(len(listings), per_tenant * 6)):
            if kept >= per_tenant:
                break
            if score_pair(t, l)["filtered"]:
                continue
            outcome, reason = simulate_outcome(t, l, rng, with_reason=True)
            tenancies.append({"tenant_id": t["id"], "listing_id": l["id"],
                              "start_date": (start + timedelta(days=rng.randint(0, 1000))).isoformat(),
                              "outcome": outcome, "dispute_reason": reason})
            kept += 1
        if i % 1000 == 0:
            print(f"  {i}/{n_tenants} tenants, {len(tenancies)} tenancies")
    return tenants, listings, tenancies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenants", type=int, default=5000)
    ap.add_argument("--listings", type=int, default=1000)
    ap.add_argument("--per-tenant", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    print(f"Generating {a.tenants} tenants and {a.listings} listings...")
    tenants, listings, tenancies = build(a.tenants, a.listings, a.per_tenant, a.seed)
    write_csv(a.out, tenants, listings, tenancies)
    write_sqlite(f"{a.out}/deservia.db", tenants, listings, tenancies)

    smooth = sum(x["outcome"] for x in tenancies) / len(tenancies)
    reasons = Counter(x["dispute_reason"] for x in tenancies if not x["outcome"])
    print(f"Saved to {a.out}/: {len(tenants)} tenants, {len(listings)} listings, "
          f"{len(tenancies)} tenancies ({smooth:.0%} smooth)")
    print("Dispute reasons:", dict(reasons.most_common()))


if __name__ == "__main__":
    main()
