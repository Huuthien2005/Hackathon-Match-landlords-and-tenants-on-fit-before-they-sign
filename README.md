# Deservia match engine (Brampton AI Innovator, Challenge 9)

Lifestyle matching for landlords and tenants: "We match on how you live, never on who you are."
Made-up data only.

## Run it

```bash
# Option A: FastAPI (API docs at /docs)
pip install -r requirements.txt
uvicorn api:app --reload
# Option B: backup with zero installs (Python 3.10+)
python server.py
```
Open http://127.0.0.1:8000. Tests: `python -m unittest discover tests`

The dataset (`data/`) and trained model (`models/`) are already included. To rebuild both:

```bash
python generate_dataset.py      # ~10 s: data/tenants.csv, listings.csv, tenancies.csv + data/deservia.db
python train.py                 # ~40 s: trains from data/deservia.db  (or: python train.py --data data  for CSVs)
```
Bigger dataset: `python generate_dataset.py --tenants 20000 --listings 3000 --per-tenant 20`

## Swipe → learn → better matches (the learning loop)

Open the **Swipe** tab. Pick "I'm a tenant" (swipe homes) or "I'm a landlord" (swipe tenants), press
**Show my 10 matches**, then ♥ / ✕ each flashcard (or use the → / ← keys).

1. **Deck**: the engine scores the whole dataset (1,000+ homes or the tenants in the landlord's region),
   the AI re-ranks the strongest 60, and the top 10 you haven't swiped become flashcards.
2. **Swipe**: each ♥ / ✕ is saved to the `feedback` table in `data/deservia.db`, with the pair's features.
3. **Personal model** (`deservia/ml/personal.py`): after 4+ swipes with at least one ♥ and one ✕, a small
   model learns what *you* like and shows it ("you care about: parking, the area"). The ranking becomes
   40% match + 40% AI + 20% your swipes.
4. **Retrain** (`deservia/ml/retrain.py`): after every 10 swipes the global AI retrains in the background
   (~12 s) on the 65,000 outcomes + everyone's swipes (each swipe counts 5×). It's re-checked on held-out
   tenants and against the four-fifths rule. **If it fails fairness, it's rejected and the old model stays.**
   A passing model is swapped in live (v1 → v2 → v3…), no restart needed.
5. **Next 10**: new cards only, ranked with the updated models.

Landlords only ever see lifestyle on a tenant card: no name, diet, work, daytime-at-home, or service-animal
status (a test checks this). A like is a preference signal, not an outcome. In production, keep a separate
"likes" model and an "outcomes" model, and audit likes for bias before they influence anyone else's ranking.

Reset: the "Reset my swipes" button, or `POST /api/feedback/reset` with `{}` for everyone.

## The dataset

| File / table | Rows (default) | What's in it |
|---|---|---|
| `tenants` | 5,000 | All 15 questionnaire answers + budget, bedrooms, ideal words, cooking smells, repair speed |
| `listings` | 1,000 | Listing form fields + the landlord's own answers (`ll_` columns) |
| `tenancies` | 65,268 | Past placements: tenant_id, listing_id, start_date, **outcome** (1 = smooth 12 months), **dispute_reason** |

Same data in two formats: CSV files (open in Excel) and SQLite (`data/deservia.db`, open with DB Browser
for SQLite or `sqlite3`). `deservia/dataset.py` reads and writes both; a test checks they load identically
and give identical scores. Dispute reasons in the default data: noise 16,001 · rent arrears 3,833 ·
repairs 1,638 · cleanliness 1,363 · smoking 1,072 · kitchen 565 · schedule 515 · pets 115.

**To use real data later:** fill the same three tables (keep the column names) and run `python train.py`.
Nothing else changes.

## The AI model

**What it predicts:** P(smooth first 12 months | tenant answers, listing, landlord answers), meaning no
dispute, no arrears and no early exit.

**How it fits in:** the rule engine gives the explainable match % (the criteria both sides set). The model
adds "🤖 X% smooth tenancy". Ranking = 50% match + 50% model. Hard filters and the fairness guard run first,
so the model only sees allowlisted features (`deservia/ml/features.py`: 35 features).

**Training data:** there are no real outcomes yet (real data is off limits), so `deservia/ml/simulate.py`
simulates tenancies from the clashes that commonly become LTB disputes: noise (much worse with the landlord
on site and a shared entrance), cleanliness gaps, smoking, rent stretch, slow repairs, kitchen friction.
In the build phase, real labels replace this file: ratings tags, conduct reports, early lease ends.

**Results** (trained on 65,268 tenancies read from `data/deservia.db`, tested on held-out tenants;
each tenant has ~13 past tenancies, so we check their top 3):

| Ranking | AUC | Smooth tenancies in top 3 |
|---|---|---|
| Random order | – | 61% |
| Rule score only | 0.698 | 78% |
| Logistic regression | 0.789 | 82% |
| **Gradient boosting (used)** | **0.801** | **84%** |

Top learned factor: noise clash when the landlord lives on site, then repair-speed gap, then rent vs budget.

**Model fairness:** the features can't guess the hidden group (AUC 0.51, where 0.5 = no information), and
good fits per top 3 by group pass the four-fifths rule (0.96). See the AI model tab and `models/model_card.json`.

**Be honest in the pitch:** the model learns the patterns we simulated; what's proven this weekend is the
pipeline (features → training → evaluation → fairness checks → serving). With Deservia's real outcomes,
the same `train.py` retrains on real data.

## How a score is made

1. **Hard filters**: rent more than 10% over budget, too few bedrooms, a pet the policy doesn't allow
   (a service animal is never a pet), a smoker in a non-smoking home, or any criterion the user marked
   "dealbreaker". Filtered listings are listed with a reason, not hidden.
2. **Criteria**: each scores 0–1: budget, area, rental type, timing, parking, smoking, pets, tidiness,
   noise, early/night, introvert/extrovert, hobbies, travel, cooking smells (shared kitchens only),
   repair speed, and the "ideal tenant/landlord" words checked against the other side's real answers.
3. **Two-way percent** = √(tenant-side × landlord-side) × 100. Each side is weighted by *its own*
   importance levels, so the percent is "the criteria both sides set". The geometric mean means a match
   has to work for both sides.
4. **Explanation**: "things in common" (lifestyle first) and a per-criterion breakdown ("Why 95%?").

## Fairness guard

| Layer | What it does | Where |
|---|---|---|
| Allowlist | Only lifestyle and home fields can reach the scorer | `fairness.SCORED_FIELDS` |
| Never scored | diet, work, days, service animal, name, with the reason for each | `fairness.NOT_SCORED` |
| Text filter | Protected-ground phrases ("no kids", "no ODSP", "Christian household") are removed and shown | `fairness.check_text` |
| Audit | Hidden group never seen by the scorer; four-fifths rule, safe vs "also scoring diet/work/days" | `audit.py` |

Current result (600 tenants × 100 listings from the dataset): lifestyle-only engine **0.996 ✓**. Also scoring
the live site's diet / work-from-home / work questions: **0.39 ✗**.

## Sunday demo script (inside the 5 minutes)

0. **Swipe tab**: swipe 10 homes as Alex; show the retrain ("Model v2 trained on 55,066 outcomes + 10 swipes,
   fairness ✓") and the "What we learned you care about" chips on the next deck. Flip to landlord view.
1. **Matches tab**: Alex (made up) vs 10 listings, ranked 100 → 57%, 5 good fits, with what they have in common.
   Open "Why 100%?" on card 1.
2. **Protected ground kept out**: point at the struck-out "no young families upstairs" and at card 2, where the
   landlord wrote "young professional couple, no ODSP". Both are kept out and the score is unchanged
   (`test_protected_phrase_does_not_change_score`). Type "no kids" live in the box.
3. Switch to **Sam**: a service dog still matches the "No pets" listings.
4. **Fairness audit tab**: 0.93 passes vs 0.51 fails. "This is why we don't score diet."
5. **AI model tab**: trained on 65,268 tenancies from the database; AI finds 84% smooth tenancies in the top 3 vs 78% for rules alone; fairness checks pass.
6. **Launch metrics tab**: what Deservia watches from day one.

## Findings for Deservia's live questionnaire

- **Q8 "How do you eat?"** (vegan/vegetarian…) and the "Pescatarian" card tag: diet can stand in for creed.
  Replace with "cooking smells", as Deservia's own PDF says.
- **Q4 work situation**: no option for people not working, so it can stand in for public assistance. Not scored.
- **Q5 where you spend your days**: can stand in for disability or caregiving. Not scored.
- **Missing questions the brief needs**: monthly budget (the "is it affordable" check), bedrooms, repair-speed
  expectations, the ideal tenant/landlord words, and importance per question.
- **Affordability** uses the tenant's own budget, never a rent-to-income ratio (the OHRC has found those
  discriminatory). Income checks stay with SingleKey.

## Connecting to deservia.netlify.app

CORS is open. The front end can `POST /api/match` with `{"tenant": {...answers...}}` and render each match's
`name, area, rental_type, price, description, match_pct, tags, in_common_count`, which is exactly what its card
shows today. Option ids are in `deservia/options.py`.

## Roadmap (continuing team)

Learn weights from outcomes: the ratings spec's tags ("Paid on time", "Cared for the home", "Quick repairs")
plus accepts and withdrawals become labels for learning-to-rank. Keep the audit as a check before every
release, encrypt questionnaire data at rest, and replace `BASE_RENT` with CMHC Rental Market Survey figures.

## Files

```
deservia/options.py    answer ids copied from the live UI
deservia/fairness.py   allowlist, never-scored list, protected-ground text filter
deservia/traits.py     ideal-words → checks against the other side's answers
deservia/engine.py     filters, criteria, two-way score, explanation
deservia/data.py       demo tenants/listings + seeded synthetic population
deservia/audit.py      four-fifths audit and launch metrics
deservia/service.py    shared request handling
api.py / server.py     FastAPI app / zero-dependency backup
static/index.html      demo page
deservia/dataset.py    read/write the dataset as CSV or SQLite
generate_dataset.py    builds data/ (tenants, listings, labelled tenancies)
data/                  tenants.csv, listings.csv, tenancies.csv, deservia.db
deservia/ml/            features, outcome simulator, model loading + re-rank
train.py               trains, evaluates, audits and saves the model
models/                match_model.joblib + model_card.json
deservia/feedback.py    swipe storage (feedback table)
deservia/ml/personal.py per-user preference model
deservia/ml/retrain.py  background retrain with fairness guardrail + hot swap
deservia/ml/trainset.py dataset -> feature matrix (+ cache for fast retrains)
tests/                 26 tests incl. fairness guarantees, CSV/SQLite round-trip, learning loop
```
