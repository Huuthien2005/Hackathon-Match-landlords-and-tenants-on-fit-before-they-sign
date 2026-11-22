"""Sign-in, roles and privacy, through the same route table both servers use. Temporary DB."""
import tempfile
import unittest
from pathlib import Path

from deservia import auth, feedback as fb


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp())
        cls._real = (auth.DB, fb.DB)
        auth.DB = fb.DB = tmp / "app.db"
        from deservia import routes, service
        cls.R, cls.service = routes, service
        service.load_users_into_pool()
        cls.agent = cls.signin("owner@deservia.ca", "admin1234")
        cls.alex = cls.signin("alex@demo.ca", "demo1234")
        cls.maple = cls.signin("maple@demo.ca", "demo1234")

    @classmethod
    def tearDownClass(cls):
        auth.DB, fb.DB = cls._real

    @classmethod
    def signin(cls, email, pw):
        s, r = cls.R.dispatch("POST", "/api/auth/signin", {"email": email, "password": pw}, None)
        assert s == 200, r
        return r["token"]

    def call(self, method, path, body=None, token=None):
        return self.R.dispatch(method, path, body or {}, token)

    def test_passwords_are_hashed(self):
        h = auth.hash_password("demo1234")
        self.assertNotIn("demo1234", h)
        self.assertTrue(auth.check_password("demo1234", h))
        self.assertFalse(auth.check_password("wrong", h))

    def test_wrong_password_and_no_token(self):
        self.assertEqual(self.call("POST", "/api/auth/signin", {"email": "alex@demo.ca", "password": "nope"})[0], 401)
        self.assertEqual(self.call("POST", "/api/deck")[0], 401)

    def test_cannot_sign_up_as_agent_or_twice(self):
        ok = {"adult": True, "privacy": True}
        self.assertEqual(self.call("POST", "/api/auth/signup", {"email": "a@b.ca", "password": "12345678", "role": "agent", **ok})[0], 400)
        self.assertEqual(self.call("POST", "/api/auth/signup", {"email": "alex@demo.ca", "password": "12345678", "role": "tenant", **ok})[0], 409)

    def test_signup_needs_18_plus_and_privacy_consent(self):
        base = {"email": "consent@t.ca", "password": "pass12345", "role": "tenant"}
        for consent in ({}, {"adult": True}, {"privacy": True}, {"adult": "yes", "privacy": True}):
            self.assertEqual(self.call("POST", "/api/auth/signup", {**base, **consent})[0], 400, consent)
        self.assertEqual(self.call("POST", "/api/auth/signup", {**base, "adult": True, "privacy": True})[0], 200)

    def test_tenants_and_landlords_cannot_reach_agent_routes(self):
        for tok in (self.alex, self.maple):
            for path in ("/api/agent/overview", "/api/admin/audit", "/api/admin/model", "/api/admin/metrics", "/api/learning"):
                self.assertEqual(self.call("GET", path, token=tok)[0], 403, path)
        self.assertEqual(self.call("GET", "/api/agent/overview", token=self.agent)[0], 200)

    def test_user_cards_have_no_ai_scores(self):
        s, d = self.call("POST", "/api/deck", token=self.alex)
        self.assertEqual(s, 200)
        self.assertEqual(len(d["cards"]), 10)
        for c in d["cards"]:
            for hidden in ("ml_success_pct", "personal_like_pct", "rank_score", "good_fit"):
                self.assertNotIn(hidden, c)
        self.assertNotIn("blend", d)

    def test_landlord_never_sees_tenant_excluded_phrases(self):
        s, d = self.call("POST", "/api/deck", token=self.maple)
        alex_card = next(c for c in d["cards"] if c["item_id"].startswith("u_"))
        self.assertEqual(alex_card["excluded"], [])          # Alex wrote "no young families upstairs"

    def test_tenant_sees_own_excluded_phrase(self):
        s, d = self.call("POST", "/api/deck", token=self.alex)
        self.assertTrue(any("families" in e["text"] for e in d["cards"][0]["excluded"]))

    def test_answers_are_validated(self):
        s, r = self.call("POST", "/api/auth/signup", {"email": "new@t.ca", "password": "pass12345", "role": "tenant",
                                                       "adult": True, "privacy": True})
        tok = r["token"]
        self.assertEqual(self.call("POST", "/api/deck", token=tok)[0], 400)              # no questionnaire yet
        s, r = self.call("POST", "/api/me/answers", {"answers": {"rental_type": "castle"}}, tok)
        self.assertEqual(s, 400)
        good = auth._tenant_answers(self.service.DEMO_TENANTS[0])
        s, me = self.call("POST", "/api/me/answers", {"answers": {**good, "diet": "vegan", "group": "B"}}, tok)
        self.assertEqual(s, 200)
        self.assertNotIn("diet", me["answers"])                                            # injected fields dropped
        self.assertNotIn("group", me["answers"])

    def test_mutual_match(self):
        fb.reset()
        _, d = self.call("POST", "/api/deck", token=self.alex)
        maple_home = next(c for c in d["cards"] if c["item_id"].startswith("ul_"))
        self.assertFalse(self.call("POST", "/api/swipe", {"item_id": maple_home["item_id"], "liked": True}, self.alex)[1]["mutual"])
        _, d2 = self.call("POST", "/api/deck", token=self.maple)
        alex_card = next(c for c in d2["cards"] if c["item_id"].startswith("u_"))
        self.assertTrue(self.call("POST", "/api/swipe", {"item_id": alex_card["item_id"], "liked": True}, self.maple)[1]["mutual"])
        _, m = self.call("GET", "/api/my-matches", token=self.alex)
        self.assertTrue(m["matches"][0]["mutual"])
        _, o = self.call("GET", "/api/agent/overview", token=self.agent)
        self.assertEqual(o["kpis"]["mutual_matches"], 1)

    def test_free_matches_then_membership(self):
        fb.reset()
        for email, role, plan, wrong in (("sam@demo.ca", "tenant", "tenant_silver", "landlord_gold"),
                                         ("sandalwood@demo.ca", "landlord", "landlord_gold", "tenant_silver")):
            tok = self.signin(email, "demo1234")
            self.call("POST", "/api/unsubscribe", token=tok)
            s, d = self.call("POST", "/api/deck", token=tok)
            self.assertEqual((s, len(d["cards"])), (200, 10))
            for c in d["cards"]:
                self.assertEqual(self.call("POST", "/api/swipe", {"item_id": c["item_id"], "liked": False}, tok)[0], 200)
            s, r = self.call("POST", "/api/deck", token=tok)              # "Show my next 10"
            self.assertEqual(s, 402)
            self.assertTrue(r["paywall"])
            ids = [p["id"] for p in r["plans"]]
            self.assertIn(plan, ids)
            self.assertNotIn(wrong, ids)                                  # tenants only see tenant plans
            self.assertEqual(self.call("POST", "/api/swipe", {"item_id": "x", "liked": True}, tok)[0], 402)
            self.assertEqual(self.call("POST", "/api/subscribe", {"plan": wrong}, tok)[0], 400)
            s, me = self.call("POST", "/api/subscribe", {"plan": plan}, tok)
            self.assertTrue(me["usage"]["unlimited"])
            s, d = self.call("POST", "/api/deck", token=tok)
            self.assertEqual((s, len(d["cards"])), (200, 10))
            self.call("POST", "/api/unsubscribe", token=tok)
        fb.reset()

    def _mutual(self):
        fb.reset()
        _, d = self.call("POST", "/api/deck", token=self.alex)
        home = next(c for c in d["cards"] if c["item_id"].startswith("ul_"))["item_id"]
        self.call("POST", "/api/swipe", {"item_id": home, "liked": True}, self.alex)
        _, d2 = self.call("POST", "/api/deck", token=self.maple)
        alex_id = next(c for c in d2["cards"] if c["item_id"].startswith("u_"))["item_id"]
        self.call("POST", "/api/swipe", {"item_id": alex_id, "liked": True}, self.maple)
        return home, alex_id

    def test_either_side_can_withdraw(self):
        for side in ("tenant", "landlord"):
            home, alex_id = self._mutual()
            _, m = self.call("GET", "/api/my-matches", token=self.alex)
            self.assertTrue(m["matches"][0]["mutual"])
            if side == "tenant":
                self.assertEqual(self.call("POST", "/api/withdraw", {"item_id": home}, self.alex)[0], 200)
            else:
                self.assertEqual(self.call("POST", "/api/withdraw", {"item_id": alex_id}, self.maple)[0], 200)
            _, o = self.call("GET", "/api/agent/overview", token=self.agent)
            self.assertEqual(o["kpis"]["mutual_matches"], 0, side)
            _, m = self.call("GET", "/api/my-matches", token=self.maple if side == "tenant" else self.alex)
            self.assertFalse(any(x["mutual"] for x in m["matches"]), side)
        self.assertEqual(self.call("POST", "/api/withdraw", {"item_id": "nothing"}, self.alex)[0], 404)
        fb.reset()

    def test_delete_account_removes_everything(self):
        s, r = self.call("POST", "/api/auth/signup", {"email": "bye@t.ca", "password": "pass12345", "role": "tenant",
                                                       "adult": True, "privacy": True})
        tok = r["token"]
        good = auth._tenant_answers(self.service.DEMO_TENANTS[0])
        self.call("POST", "/api/me/answers", {"answers": good}, tok)
        pid = next(u["pool_id"] for u in auth.list_users() if u["email"] == "bye@t.ca")
        _, d = self.call("POST", "/api/deck", token=tok)
        self.call("POST", "/api/swipe", {"item_id": d["cards"][0]["item_id"], "liked": True}, tok)
        self.assertIn(pid, self.service.ALL_TENANTS)
        self.assertEqual(self.call("POST", "/api/me/delete", {"password": "wrong"}, tok)[0], 400)
        self.assertEqual(self.call("GET", "/api/me", token=tok)[0], 200)     # still signed in after a typo
        self.assertEqual(self.call("POST", "/api/me/delete", {"password": "pass12345"}, tok)[0], 200)
        self.assertNotIn("bye@t.ca", [u["email"] for u in auth.list_users()])
        self.assertNotIn(pid, self.service.ALL_TENANTS)                 # gone from everyone's matching pool
        self.assertEqual(fb.counts(pid)["swipes"], 0)
        self.assertEqual(self.call("GET", "/api/me", token=tok)[0], 401)  # token no longer works
        self.assertEqual(self.call("POST", "/api/auth/signin", {"email": "bye@t.ca", "password": "pass12345"})[0], 401)
        self.assertEqual(self.call("POST", "/api/me/delete", {"password": "admin1234"}, self.agent)[0], 403)

    def test_sign_in_is_rate_limited(self):
        email = "sandalwood@demo.ca"
        codes = [self.call("POST", "/api/auth/signin", {"email": email, "password": "nope"})[0] for _ in range(9)]
        self.assertEqual(codes[:8], [401] * 8)
        self.assertEqual(codes[8], 429)
        auth._fails.clear()

    def test_config_hides_owner_login_when_secret_is_set(self):
        import os
        self.assertIsNotNone(self.call("GET", "/api/config")[1]["owner_hint"])      # local default
        os.environ["DESERVIA_ADMIN_PASSWORD"] = "x-secret"
        try:
            self.assertIsNone(self.call("GET", "/api/config")[1]["owner_hint"])
        finally:
            del os.environ["DESERVIA_ADMIN_PASSWORD"]

    def test_signout_kills_token(self):
        tok = self.signin("alex@demo.ca", "demo1234")
        self.call("POST", "/api/auth/signout", token=tok)
        self.assertEqual(self.call("GET", "/api/me", token=tok)[0], 401)


if __name__ == "__main__":
    unittest.main()
