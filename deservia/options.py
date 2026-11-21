"""Answer options, copied from the live Deservia UI (deservia.netlify.app) so the API
accepts exactly what the front end sends. Values are snake_case ids; labels are for display."""

RENTAL_TYPES = {
    "room": "A room", "apartment": "Apartment", "basement": "Basement apartment",
    "whole_house": "Whole house", "upper_floor": "Upper floor", "rent_to_own": "Rent-to-own",
}

AREAS = {
    "Ontario – Toronto": ["Downtown Toronto", "North York", "Scarborough", "Etobicoke"],
    "Ontario – Peel Region": ["Mississauga", "Brampton", "Caledon"],
    "Ontario – York Region": ["Markham", "Vaughan"],
    "Ontario – Southern & Central": ["Hamilton", "Guelph", "London", "Niagara Region", "Grey County"],
}
AREA_TO_REGION = {a: r for r, areas in AREAS.items() for a in areas}

HOBBIES = ["Gardening", "Fishing", "Painting", "Artistic / creative", "Building websites / tech",
           "Music", "Travel", "Cooking", "Fitness", "Reading"]

# Q4-Q15 of the live questionnaire
WORK = ["student", "employed", "self_employed"]            # stored, NOT scored (see fairness.py)
DAYS = ["work_from_home", "out", "mix"]                    # stored, NOT scored (see fairness.py)
PETS = ["love_pets", "have_pet", "prefer_no_pets"]
PET_KIND = ["dog", "cat", "small", "other"]                # added: needed to check "Cats only" etc.
SMOKING = ["non_smoker", "outdoor_only", "smoker"]
DIET = ["vegan", "vegetarian", "pescatarian", "fruitarian", "no_restrictions"]  # NOT scored
CHRONOTYPE = ["early", "night", "flexible"]
SOCIAL = ["introvert", "extrovert", "both"]
TIDY = ["relaxed", "reasonably", "very"]                   # ordinal low -> high
MUSIC = ["love_music", "quiet"]
TRAVEL = ["love_travel", "homebody"]
DRIVE = ["drives", "non_driver"]
TIMING = ["within_month", "1_3_months", "flexible"]

# Added from Deservia's official questionnaire PDF (missing from the live site)
COOKING_SMELLS = ["rarely_cook", "light", "strong"]        # replaces "How do you eat?" for shared kitchens
REPAIR_SPEED = ["same_day", "24h", "week", "no_pref"]      # tenant: expects / landlord: commits to

# Listing form ("List your home")
PARKING = ["none", "street", "one", "two_plus", "garage"]
PET_POLICY = ["welcome", "cats_only", "dogs_only", "small_only", "none"]
SMOKE_POLICY = ["non_smoking", "outside_only", "allowed"]
KITCHEN = ["private", "shared", "kitchenette"]
ENTRANCE = ["separate", "shared"]
FURNISHED = ["furnished", "partly", "unfurnished"]
LEASE = ["month_to_month", "6_months", "1_year", "2_plus", "flexible"]

# Importance a user can give each criterion (OkCupid-style)
IMPORTANCE = {"irrelevant": 0, "a_little": 1, "somewhat": 3, "very": 10, "dealbreaker": 25}
