"""Every API route, its access level, and its handler, shared by api.py (FastAPI) and server.py.

Access levels:
  public   - sign up, sign in, questionnaire definitions
  user     - signed-in tenant or landlord: own profile, deck, swipes, matches
  agent    - the website owner: analytics, audit, AI model, metrics, retraining

Tenants and landlords never receive AI scores, the audit or metrics: `_public_card` strips them.
"""
from . import auth, feedback as fb, plans, service
from .auth import AuthError
from .questionnaire import describe, questions, validate

USER_CARD_KEYS = ("item_id", "match_pct", "in_common", "in_common_count", "flags", "excluded", "notes",
                  "name", "area", "rental_type", "price", "price_label", "description", "tags")
RETRAIN_EVERY = 10


class ApiError(Exception):
    def __init__(self, status, message, extra=None):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra or {}


def _public_card(c, viewer_role):
    """Strip AI scores, and show each person only THEIR OWN excluded phrases: a landlord never
    sees what a tenant wrote (or the reverse). Notes about the other side are dropped too."""
    out = {k: c.get(k) for k in USER_CARD_KEYS}
    out["excluded"] = [{"text": e["text"], "ground": e["ground"]} for e in c.get("excluded", []) if e.get("from") == viewer_role]
    out["notes"] = [n for n in c.get("notes", []) if n.startswith("Service/support animal")]
    return out


def _need_profile(user):
    if not user.get("answers"):
        raise ApiError(400, "Finish your questionnaire first")


def _usage(user):
    used = fb.counts(user["pool_id"])["swipes"] if user.get("pool_id") else 0
    paid = plans.is_paid(user.get("plan"))
    return {"plan": user.get("plan", "free"), "plan_name": plans.PLANS.get(user.get("plan", "free"), plans.PLANS["free"])["name"],
            "free_limit": plans.FREE_MATCHES, "used": used, "unlimited": paid,
            "remaining": None if paid else max(0, plans.FREE_MATCHES - used)}


def _need_matches_left(user):
    """Free accounts get FREE_MATCHES swipes. After that, 402 + the plans for this role."""
    u = _usage(user)
    if not u["unlimited"] and u["used"] >= plans.FREE_MATCHES:
        raise ApiError(402, f"You've used your {plans.FREE_MATCHES} free matches. Choose a plan to keep matching.",
                       {"paywall": True, "plans": plans.for_role(user["role"]), "usage": u})


# ------------------------------------------------------------------ public
def signup(body, _):
    if body.get("adult") is not True or body.get("privacy") is not True:
        raise ApiError(400, "Please confirm you're 18 or older and agree to the Privacy Policy")
    auth.signup(body.get("email"), body.get("password"), body.get("role"), consent=True)
    token = auth.signin(body.get("email"), body.get("password"))
    return {"token": token, "me": me(None, auth.user_from_token(token))}


def signin(body, _):
    token = auth.signin(body.get("email"), body.get("password"))
    return {"token": token, "me": me(None, auth.user_from_token(token))}


def get_questions(body, _):
    role = body.get("role")
    if role not in ("tenant", "landlord"):
        raise ApiError(400, "role must be tenant or landlord")
    return questions(role)


def health(_, __):
    return {"ok": True}


def config(_, __):
    """What the sign-in page may show. The owner login is only listed when it still uses the local
    default password; on a public deployment (DESERVIA_ADMIN_PASSWORD set) it is never shown."""
    import os
    accounts = [{"role": "tenant", "email": "alex@demo.ca"}, {"role": "tenant", "email": "sam@demo.ca"},
                {"role": "landlord", "email": "maple@demo.ca"}, {"role": "landlord", "email": "sandalwood@demo.ca"}]
    return {"demo_password": "demo1234", "demo_accounts": accounts,
            "owner_hint": {"email": "owner@deservia.ca", "password": "admin1234"} if auth.owner_password_is_default() else None,
            "public_demo": os.environ.get("DESERVIA_PUBLIC_DEMO") == "1"}


# ------------------------------------------------------------------ signed-in user
def me(_, user):
    a = user.get("answers")
    out = {"email": user["email"], "role": user["role"], "has_profile": bool(a), "answers": a,
           "answers_view": describe(user["role"], a) if a else []}
    if user["role"] in ("tenant", "landlord"):
        out["usage"] = _usage(user)
    return out


def signout(_, user, token=None):
    auth.signout(token)
    return {"signed_out": True}


def save_answers(body, user):
    if user["role"] not in ("tenant", "landlord"):
        raise ApiError(403, "Only tenants and landlords have a questionnaire")
    clean, errors = validate(user["role"], body.get("answers") or {})
    if errors:
        raise ApiError(400, "; ".join(errors[:3]))
    auth.save_answers(user["id"], clean)
    user = auth.get_user(user["id"])
    service.register_user(user)
    return me(None, user)


def check_text(body, _):
    return service.check(body)


def deck(body, user):
    _need_profile(user)
    _need_matches_left(user)
    req = {"role": user["role"], "user_id": user["pool_id"], "limit": 10}
    if user["role"] == "tenant":
        req["tenant"] = service.ALL_TENANTS[user["pool_id"]]
    d = service.deck(req)
    return {"cards": [_public_card(c, user["role"]) for c in d["cards"]], "remaining": d["remaining"],
            "you_seem_to_like": [x["words"] for x in d["learned"]], "swipes": d["swipes"], "usage": _usage(user)}


def swipe(body, user):
    _need_profile(user)
    _need_matches_left(user)
    out = service.swipe({"user_id": user["pool_id"], "item_id": body.get("item_id"), "liked": body.get("liked")})
    n = out["swipes"]["swipes"]
    if n and n % RETRAIN_EVERY == 0:          # learn from every 10 swipes, silently
        service.retrain()
    item = body.get("item_id")
    mutual = False
    if body.get("liked"):
        mutual = (fb.has_like(item, user["pool_id"], item) if user["role"] == "tenant"
                  else fb.has_like(item, item, user["pool_id"]))
    return {"saved": True, "swipes": out["swipes"], "mutual": mutual, "usage": _usage(auth.get_user(user["id"]))}


def my_matches(_, user):
    """Who/what you liked, and whether it's mutual (both sides liked each other)."""
    out = []
    for tid, lid, pct in fb.liked(user["pool_id"]):
        if user["role"] == "tenant":
            other, item = lid, service.ALL_LISTINGS.get(lid, {})
            name, sub = item.get("title", lid), f'{item.get("area", "")} · ${item.get("rent", "")}/mo'
            mutual = fb.has_like(lid, tid, lid)
        else:
            other, item = tid, service.ALL_TENANTS.get(tid, {})
            name, sub = f'Tenant in {item.get("area", "?")}', f'Budget ${item.get("budget", "")}'
            mutual = fb.has_like(tid, tid, lid)
        real = other.startswith("u")
        out.append({"item_id": other, "name": name, "sub": sub, "match_pct": pct, "mutual": mutual,
                    "status": "Mutual match 🎉 Your Deservia agent will reach out to book a viewing." if mutual
                    else ("Waiting for them to swipe" if real else "Liked (sample listing)")})
    return {"matches": out}


def withdraw(body, user):
    """Either side can withdraw a like at any time; a mutual match stops being mutual."""
    _need_profile(user)
    item = body.get("item_id") or ""
    tid, lid = (user["pool_id"], item) if user["role"] == "tenant" else (item, user["pool_id"])
    if not fb.withdraw(user["pool_id"], tid, lid):
        raise ApiError(404, "Nothing to withdraw")
    return {"withdrawn": True}


def delete_account(body, user):
    """PIPEDA right to deletion: needs the password again. Removes the account, answers, swipes
    (including other people's swipes on this person) and sessions."""
    if user["role"] == "agent":
        raise ApiError(403, "The owner account can't be deleted here")
    if not auth.verify_password(user["id"], body.get("password")):
        raise ApiError(400, "Wrong password")      # not 401: that would read as "session expired" and sign out
    fb.delete_everything_about(user["pool_id"])
    service.unregister_user(user["pool_id"])
    auth.delete_user(user["id"])
    return {"deleted": True}


def list_plans(_, user):
    return {"plans": plans.for_role(user["role"]), "usage": _usage(user)}


def subscribe(body, user):
    """DEMO checkout: no card, no payment. Stripe replaces this in the build phase."""
    plan = body.get("plan")
    if user["role"] not in ("tenant", "landlord") or not plans.can_subscribe(user["role"], plan):
        raise ApiError(400, "That plan isn't available for your account")
    auth.set_plan(user["id"], plan)
    return {**me(None, auth.get_user(user["id"])), "demo_checkout": True}


def unsubscribe(_, user):
    auth.set_plan(user["id"], "free")
    return me(None, auth.get_user(user["id"]))


# ------------------------------------------------------------------ agent
def agent_overview(_, __):
    from .analytics import overview
    return overview()


def agent_rules_demo(body, _):
    return service.match(body)


ROUTES = {
    ("GET", "/api/health"): (health, "public"),
    ("GET", "/api/config"): (config, "public"),
    ("POST", "/api/auth/signup"): (signup, "public"),
    ("POST", "/api/auth/signin"): (signin, "public"),
    ("POST", "/api/questions"): (get_questions, "public"),
    ("GET", "/api/me"): (me, "user"),
    ("POST", "/api/auth/signout"): (signout, "user"),
    ("POST", "/api/me/answers"): (save_answers, "user"),
    ("POST", "/api/check-text"): (check_text, "user"),
    ("POST", "/api/deck"): (deck, "user"),
    ("POST", "/api/swipe"): (swipe, "user"),
    ("GET", "/api/my-matches"): (my_matches, "user"),
    ("GET", "/api/plans"): (list_plans, "user"),
    ("POST", "/api/withdraw"): (withdraw, "user"),
    ("POST", "/api/me/delete"): (delete_account, "user"),
    ("POST", "/api/subscribe"): (subscribe, "user"),
    ("POST", "/api/unsubscribe"): (unsubscribe, "user"),
    ("GET", "/api/agent/overview"): (agent_overview, "agent"),
    ("GET", "/api/admin/audit"): (lambda b, u: service.audit(), "agent"),
    ("GET", "/api/admin/metrics"): (lambda b, u: service.metrics(), "agent"),
    ("GET", "/api/admin/model"): (lambda b, u: service.model_card(), "agent"),
    ("GET", "/api/learning"): (lambda b, u: service.learning_status(), "agent"),
    ("POST", "/api/retrain"): (lambda b, u: service.retrain(), "agent"),
    ("POST", "/api/feedback/reset"): (lambda b, u: service.reset_feedback(b), "agent"),
    ("GET", "/api/tenants"): (lambda b, u: service.list_tenants(), "agent"),
    ("POST", "/api/match"): (agent_rules_demo, "agent"),
}


def dispatch(method, path, body, token):
    """Returns (status, payload). Never raises."""
    route = ROUTES.get((method, path))
    if not route:
        return 404, {"detail": "Not found"}
    handler, level = route
    try:
        user = auth.user_from_token(token) if level != "public" else None
        if level != "public" and not user:
            return 401, {"detail": "Please sign in"}
        if level == "user" and user["role"] not in ("tenant", "landlord", "agent"):
            return 403, {"detail": "Not allowed"}
        if level == "agent" and user["role"] != "agent":
            return 403, {"detail": "Agents only"}
        if handler is signout:
            return 200, signout(body, user, token)
        return 200, handler(body or {}, user)
    except ApiError as e:
        return e.status, {"detail": e.message, **e.extra}
    except AuthError as e:
        return e.status, {"detail": e.message}
    except KeyError as e:
        return 404, {"detail": str(e).strip("'")}
    except (ValueError, TypeError) as e:
        return 400, {"detail": f"Bad request: {e}"}
