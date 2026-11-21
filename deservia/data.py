"""Made-up data only. No real person's data (challenge rule).

- DEMO_TENANTS / DEMO_LISTINGS: hand-written for Sunday's demo (1 tenant vs 10 listings,
  plus protected-ground phrases that must be kept out of the score).
- generate(): a seeded synthetic population for the fairness audit and metrics. Each
  synthetic person carries a hidden `group` the scorer never sees, correlated with diet,
  daytime-at-home and work, the way real-world stand-ins correlate with protected grounds.

Rents: placeholder Brampton-area figures by type and bedrooms. Replace BASE_RENT with
CMHC Rental Market Survey values (Toronto CMA, Brampton zones) before the pitch if you can.
"""
import random

from .options import HOBBIES

BASE_RENT = {  # (rental_type, bedrooms) -> monthly rent, CAD (placeholder, see docstring)
    ("room", 1): 950, ("basement", 1): 1650, ("basement", 2): 1950, ("apartment", 1): 2050,
    ("apartment", 2): 2500, ("upper_floor", 2): 2400, ("upper_floor", 3): 2800,
    ("whole_house", 3): 3300, ("whole_house", 4): 3700,
}

DEMO_TENANTS = [
    {"id": "t_demo", "name": "Alex (made up)", "role": "tenant",
     "rental_type": "basement", "area": "Brampton", "budget": 1800, "bedrooms_needed": 1,
     "hobbies": ["Gardening", "Reading", "Cooking"], "work": "employed", "days": "out",
     "pets": "love_pets", "smoking": "non_smoker", "diet": "vegetarian",
     "chronotype": "early", "social": "introvert", "tidy": "very", "music": "quiet",
     "travel": "homebody", "drive": "drives", "timing": "1_3_months",
     "cooking_smells": "light", "repair_speed": "24h",
     "ideal_text": "quiet, tidy, fixes things fast - no young families upstairs, respectful",
     "importance": {"budget": "very", "tidy": "very"}},
    {"id": "t_sam", "name": "Sam (made up)", "role": "tenant",
     "rental_type": "basement", "area": "Brampton", "budget": 1800, "bedrooms_needed": 1,
     "hobbies": ["Reading", "Building websites / tech"], "work": "self_employed", "days": "work_from_home",
     "pets": "have_pet", "pet_kind": "dog", "service_animal": True, "smoking": "non_smoker",
     "chronotype": "flexible", "social": "both", "tidy": "very", "music": "quiet",
     "travel": "homebody", "drive": "non_driver", "timing": "flexible",
     "cooking_smells": "rarely_cook", "repair_speed": "24h", "ideal_text": "quiet, responsive"},
]


def _ll(**kw):
    base = {"role": "landlord", "smoking": "non_smoker", "pets": "love_pets", "chronotype": "flexible",
            "social": "both", "tidy": "reasonably", "music": "quiet", "travel": "homebody",
            "hobbies": [], "cooking_smells": "light", "repair_speed": "24h", "ideal_text": ""}
    base.update(kw)
    return base


DEMO_LISTINGS = [
    {"id": "l01", "title": "Maple Lane basement suite", "area": "Brampton", "rental_type": "basement",
     "rent": 1700, "bedrooms": 1, "parking": "one", "kitchen": "private", "entrance": "separate",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": True,
     "description": "Bright, quiet basement with a separate entrance, 5 min walk to the bus.",
     "landlord": _ll(chronotype="early", social="introvert", tidy="very", hobbies=["Gardening", "Reading"],
                     repair_speed="same_day", ideal_text="tidy, quiet, non-smoker")},
    {"id": "l02", "title": "Sandalwood garden basement", "area": "Brampton", "rental_type": "basement",
     "rent": 1650, "bedrooms": 1, "parking": "one", "kitchen": "private", "entrance": "separate",
     "pet_policy": "small_only", "smoke_policy": "non_smoking", "timing": "flexible", "landlord_on_site": True,
     "description": "Cosy suite, backyard garden, landlord upstairs.",
     "landlord": _ll(chronotype="night", social="extrovert", tidy="very", hobbies=["Gardening", "Cooking"],
                     ideal_text="clean, communicative, friendly")},
    {"id": "l03", "title": "Heart Lake 1-bed lower level", "area": "Brampton", "rental_type": "basement",
     "rent": 1750, "bedrooms": 1, "parking": "one", "kitchen": "private", "entrance": "separate",
     "pet_policy": "none", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": True,
     "description": "Renovated lower level near Heart Lake.",
     "landlord": _ll(tidy="very", chronotype="early", social="introvert", hobbies=["Reading"],
                     repair_speed="same_day",
                     ideal_text="Looking for a young professional couple, no ODSP, tidy, quiet")},
    {"id": "l04", "title": "Springdale walk-out", "area": "Brampton", "rental_type": "basement",
     "rent": 1950, "bedrooms": 1, "parking": "two_plus", "kitchen": "private", "entrance": "separate",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": True,
     "description": "Walk-out basement with patio, big windows.",
     "landlord": _ll(chronotype="early", social="introvert", tidy="very", hobbies=["Reading"])},
    {"id": "l05", "title": "Downtown Brampton party-friendly room", "area": "Brampton", "rental_type": "basement",
     "rent": 1500, "bedrooms": 1, "parking": "street", "kitchen": "shared", "entrance": "shared",
     "pet_policy": "welcome", "smoke_policy": "outside_only", "timing": "within_month", "landlord_on_site": True,
     "description": "Lively house near the GO station.",
     "landlord": _ll(chronotype="night", social="extrovert", tidy="relaxed", music="love_music",
                     travel="love_travel", cooking_smells="strong", repair_speed="week",
                     hobbies=["Music", "Travel"])},
    {"id": "l06", "title": "Bramalea basement, transit only", "area": "Brampton", "rental_type": "basement",
     "rent": 1550, "bedrooms": 1, "parking": "none", "kitchen": "private", "entrance": "separate",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": False,
     "description": "Steps from Bramalea terminal. No parking.",
     "landlord": _ll(tidy="reasonably", chronotype="night", social="extrovert", music="love_music",
                     ideal_text="tidy, honest")},
    {"id": "l07", "title": "Meadowvale 1-bed apartment", "area": "Mississauga", "rental_type": "apartment",
     "rent": 1800, "bedrooms": 1, "parking": "one", "kitchen": "private", "entrance": "shared",
     "pet_policy": "cats_only", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": False,
     "description": "Condo apartment near Meadowvale Town Centre.",
     "landlord": _ll(chronotype="night", tidy="reasonably", repair_speed="week", travel="love_travel")},
    {"id": "l08", "title": "Room in shared house, Castlemore", "area": "Brampton", "rental_type": "room",
     "rent": 900, "bedrooms": 1, "parking": "street", "kitchen": "shared", "entrance": "shared",
     "pet_policy": "none", "smoke_policy": "allowed", "timing": "within_month", "landlord_on_site": True,
     "description": "Furnished room, shared kitchen.",
     "landlord": _ll(smoking="smoker", chronotype="night", tidy="relaxed", music="love_music",
                     cooking_smells="strong", hobbies=["Fitness"])},
    {"id": "l09", "title": "Bolton upper floor", "area": "Caledon", "rental_type": "upper_floor",
     "rent": 1790, "bedrooms": 2, "parking": "garage", "kitchen": "private", "entrance": "separate",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "flexible", "landlord_on_site": True,
     "description": "Upper floor of a quiet house in Bolton.",
     "landlord": _ll(chronotype="flexible", social="both", tidy="reasonably", music="love_music",
                     hobbies=["Gardening", "Fishing"])},
    {"id": "l10", "title": "Fletcher's Meadow basement", "area": "Brampton", "rental_type": "basement",
     "rent": 1600, "bedrooms": 1, "parking": "one", "kitchen": "private", "entrance": "separate",
     "pet_policy": "none", "smoke_policy": "non_smoking", "timing": "1_3_months", "landlord_on_site": True,
     "description": "Clean basement in a family neighbourhood.",
     "landlord": _ll(tidy="reasonably", chronotype="night", music="love_music", hobbies=["Fitness"],
                     ideal_text="Christian household preferred, quiet, tidy")},
    # two that the hard filters remove (shown under filtered_out)
    {"id": "l11", "title": "Downtown Toronto condo", "area": "Downtown Toronto", "rental_type": "apartment",
     "rent": 2600, "bedrooms": 1, "parking": "none", "kitchen": "private", "entrance": "shared",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "flexible", "landlord_on_site": False,
     "description": "High-rise, lake view.", "landlord": _ll()},
    {"id": "l12", "title": "Mount Pleasant studio", "area": "Brampton", "rental_type": "basement",
     "rent": 1400, "bedrooms": 0, "parking": "one", "kitchen": "kitchenette", "entrance": "separate",
     "pet_policy": "welcome", "smoke_policy": "non_smoking", "timing": "flexible", "landlord_on_site": True,
     "description": "Compact studio.", "landlord": _ll()},
]


# ---------------------------------------------------------------- synthetic population
_PEEL = ["Brampton"] * 6 + ["Mississauga"] * 3 + ["Caledon"] + ["Etobicoke", "Vaughan"]
_TYPES = [("basement", 1), ("basement", 2), ("apartment", 1), ("apartment", 2), ("room", 1),
          ("upper_floor", 2), ("upper_floor", 3), ("whole_house", 3)]


def _lifestyle(r: random.Random, group: str) -> dict:
    """Lifestyle answers are independent of group. Diet, days and work are NOT: they are the
    stand-ins the audit must catch if anyone ever scores them."""
    b = group == "B"
    return {
        "hobbies": r.sample(HOBBIES, r.randint(1, 4)),
        "pets": r.choices(["love_pets", "have_pet", "prefer_no_pets"], [4, 3, 3])[0],
        "smoking": r.choices(["non_smoker", "outdoor_only", "smoker"], [8, 1.5, 0.5])[0],
        "chronotype": r.choice(["early", "night", "flexible"]),
        "social": r.choice(["introvert", "extrovert", "both"]),
        "tidy": r.choices(["relaxed", "reasonably", "very"], [2, 5, 3])[0],
        "music": r.choice(["love_music", "quiet"]),
        "travel": r.choice(["love_travel", "homebody"]),
        "cooking_smells": r.choice(["rarely_cook", "light", "strong"]),
        "repair_speed": r.choice(["same_day", "24h", "week", "no_pref"]),
        "diet": r.choices(["vegetarian", "no_restrictions", "vegan"], [7, 2, 1] if b else [1.5, 8, 0.5])[0],
        "days": r.choices(["work_from_home", "out", "mix"], [5, 3, 2] if b else [2, 6, 2])[0],
        "work": r.choices(["student", "employed", "self_employed"], [4, 4, 2] if b else [1, 7, 2])[0],
        "group": group,  # hidden; the scorer's allowlist never lets it through
    }


_STREETS = ["Sandalwood", "Bovaird", "Queen St", "Main St", "Chinguacousy", "Mayfield", "Countryside",
            "Williams Pkwy", "Kennedy Rd", "Dixie Rd", "Hurontario", "Mavis Rd", "Britannia", "Eglinton",
            "Heart Lake", "Springdale", "Castlemore", "Fletcher's Creek", "Mount Pleasant", "Credit Valley"]
_ADJ = ["Bright", "Cosy", "Quiet", "Renovated", "Spacious", "Sunny", "Modern", "Clean", "Charming", "Updated"]
_TYPE_WORD = {"basement": "basement suite", "apartment": "apartment", "room": "room", "upper_floor": "upper floor",
              "whole_house": "house", "rent_to_own": "rent-to-own home"}


def _describe(l):
    bits = [f'{l["bedrooms"]}-bed' if l["bedrooms"] else "studio",
            "separate entrance" if l.get("entrance") == "separate" else "shared entrance",
            {"private": "private kitchen", "shared": "shared kitchen", "kitchenette": "kitchenette"}[l["kitchen"]],
            {"none": "no parking", "street": "street parking", "one": "1 parking spot",
             "two_plus": "2+ parking spots", "garage": "garage"}[l["parking"]]]
    if l["landlord_on_site"]:
        bits.append("landlord lives on site")
    return ", ".join(bits).capitalize() + "."


def generate(n_tenants=200, n_listings=60, seed=7):
    r = random.Random(seed)
    listings = []
    for i in range(n_listings):
        rtype, beds = r.choice(_TYPES)
        ll = {"role": "landlord", **_lifestyle(r, "A" if r.random() < 0.85 else "B")}
        ll["ideal_text"] = ", ".join(r.sample(["tidy", "quiet", "non-smoker", "respectful",
                                               "communicative", "pet friendly", "calm"], 2))
        if r.random() < 0.15:  # some landlords write what they must not ask for
            ll["ideal_text"] += ", " + r.choice(["no kids", "young professionals only", "no ODSP",
                                                 "Canadian citizens preferred", "single person only"])
        listings.append({
            "id": f"s_l{i:03d}", "area": r.choice(_PEEL),
            "rental_type": rtype, "bedrooms": beds,
            "rent": int(round(BASE_RENT[(rtype, beds)] * r.uniform(0.9, 1.1), -1)),
            "parking": r.choice(["none", "street", "one", "two_plus", "garage"]),
            "kitchen": "shared" if rtype == "room" else r.choice(["private", "private", "shared"]),
            "entrance": "shared" if rtype == "room" else r.choice(["separate", "separate", "shared"]),
            "pet_policy": r.choice(["welcome", "welcome", "cats_only", "small_only", "none"]),
            "smoke_policy": r.choices(["non_smoking", "outside_only", "allowed"], [7, 2, 1])[0],
            "timing": r.choice(["within_month", "1_3_months", "flexible"]),
            "landlord_on_site": rtype in ("basement", "room", "upper_floor"),
            "landlord": ll,
        })
        l = listings[-1]
        l["title"] = f'{r.choice(_ADJ)} {_TYPE_WORD[rtype]} near {r.choice(_STREETS)}'
        l["description"] = _describe(l)
    tenants = []
    for i in range(n_tenants):
        rtype, beds = r.choice(_TYPES)
        t = {"id": f"s_t{i:03d}", "role": "tenant", **_lifestyle(r, r.choice("AB"))}
        if t["pets"] == "have_pet":
            t["pet_kind"] = r.choice(["dog", "cat", "small"])
            if r.random() < 0.06:          # a few tenants' animal is a service / support animal
                t["service_animal"] = True
        t.update({
            "rental_type": rtype, "area": r.choice(_PEEL), "bedrooms_needed": beds,
            "budget": int(round(BASE_RENT[(rtype, beds)] * r.uniform(0.9, 1.3), -1)),
            "drive": r.choice(["drives", "non_driver"]),
            "timing": r.choice(["within_month", "1_3_months", "flexible"]),
            "ideal_text": ", ".join(r.sample(["quiet", "responsive", "tidy", "fair", "friendly",
                                              "private", "pet friendly"], 2)),
        })
        tenants.append(t)
    return tenants, listings
