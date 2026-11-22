"""Membership plans and the free-match limit.

Everyone gets FREE_MATCHES swipes. After that, "Show my next 10" asks the user to subscribe.
Checkout is a DEMO: no card is collected and no payment is taken. In the build phase this is
replaced by Stripe (Deservia's policy: card details go to Stripe, never to Deservia).
"""
FREE_MATCHES = 10

PLANS = {
    "free": {"name": "Everyone", "price": "$0", "unit": "free forever", "role": "any",
             "perks": ["Create a lifestyle profile", f"{FREE_MATCHES} free matches", "Swipe on matches", "Mutual-match alerts"]},
    "tenant_silver": {"name": "Tenant Silver", "price": "$9.99", "unit": "/month", "role": "tenant",
                      "perks": ["Everything in Free", "Unlimited matches", "See who liked you", "Priority in match queue"]},
    "landlord_gold": {"name": "Landlord Gold", "price": "$29.99", "unit": "/listing · 30 days", "role": "landlord",
                      "perks": ["Unlimited tenant matches", "Featured listing", "Match insights", "Shareable listing link"]},
    "landlord_platinum": {"name": "Landlord Platinum", "price": "$49.99", "unit": "/listing · 60 days", "role": "landlord",
                          "perks": ["Everything in Gold", "Top placement 60 days", "Tenant screening add-on", "Human stager referral"]},
}


def for_role(role):
    """Plans a tenant or landlord can see, Free first."""
    return [{"id": k, **v} for k, v in PLANS.items() if v["role"] in ("any", role)]


def can_subscribe(role, plan_id):
    return plan_id in PLANS and plan_id != "free" and PLANS[plan_id]["role"] == role


def is_paid(plan_id):
    return bool(plan_id) and plan_id != "free" and plan_id in PLANS
