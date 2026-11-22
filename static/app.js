// Deservia front end: sign in -> (tenant | landlord) questionnaire + swipe, or (agent) console.
// Tenants and landlords only ever receive match %, things in common and lifestyle tags from the API.
const API = location.origin.startsWith("http") ? "" : "http://127.0.0.1:8000";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const ICON = {"Basement apartment":"🏡","Apartment":"🏢","A room":"🚪","Upper floor":"🪜","Whole house":"🏠","Rent-to-own":"🔑"};
const pctColor = (p) => p >= 80 ? "var(--green)" : p >= 65 ? "var(--amber)" : "var(--grey)";

const store = {
  get() { try { return localStorage.getItem("deservia_token"); } catch { return null; } },
  set(t) { try { t ? localStorage.setItem("deservia_token", t) : localStorage.removeItem("deservia_token"); } catch {} },
};
const S = { token: store.get(), me: null };

async function api(path, body) {
  const opts = { headers: { "Content-Type": "application/json" } };
  if (S.token) opts.headers.Authorization = "Bearer " + S.token;
  if (body !== undefined) { opts.method = "POST"; opts.body = JSON.stringify(body); }
  const r = await fetch(API + path, opts);
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && S.token) { signOutLocal(); throw new Error("Please sign in again"); }
  if (!r.ok) { const e = new Error(data.detail || ("Error " + r.status)); e.status = r.status; e.data = data; throw e; }
  return data;
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

// ================================================================ header + routing
function setNav(items, active) {
  const nav = $("nav");
  const footAuth = document.querySelector('footer [data-go="auth"]');   // "Sign in" in the footer only when signed out
  if (footAuth) footAuth.style.display = S.me ? "none" : "";
  if (!S.me) {                                   // public header (from the front-end hand-off)
    nav.innerHTML = `<a class="link" data-v="home">Home</a><a class="link" data-v="how">How it works</a>
      <a class="link" data-v="privacy">Privacy</a><button data-v="signin">Sign in</button>
      <button class="cta" data-v="signup">Get started free</button>`;
  } else {
    nav.innerHTML = items.map(([id, label]) => `<button data-v="${id}" class="${id === active ? "on" : ""}">${label}</button>`).join("") +
      `<span class="who"><span class="badge ${S.me.role === "agent" ? "agent" : ""}">${esc(S.me.role)}</span> ${esc(S.me.email)}</span>
       <button data-v="signout">Sign out</button>`;
  }
  nav.querySelectorAll("[data-v]").forEach(b => b.onclick = () => {
    const v = b.dataset.v;
    if (v === "signout") return signOut();
    if (v === "signin") return go("auth", { mode: "signin" });
    if (v === "signup") return go("auth", { mode: "signup" });
    if (v === "how") { go("home"); return setTimeout(() => $("how")?.scrollIntoView({ behavior: "smooth" }), 50); }
    go(v);
  });
}

// Where a signed-in person "lives" in the app
const homeView = () => !S.me ? "home" : S.me.role === "agent" ? "overview" : (S.me.has_profile ? "discover" : "questionnaire");

// Any "match" action from the public pages lands here: sign in first.
function startMatching(role) {
  if (S.me) return go(homeView());
  go("auth", { mode: "signup", role, notice: "Create a free account (or sign in) to start matching." });
}

async function boot() {
  try { S.config = await api("/api/config"); } catch { S.config = {}; }
  if (S.config.public_demo && !document.querySelector(".demo-banner")) {
    const b = document.createElement("div");
    b.className = "demo-banner";
    b.textContent = "Demo with made-up data for the Brampton AI Innovator challenge. Please don't enter real personal information.";
    document.body.prepend(b);
  }
  if (S.token) {
    try { S.me = await api("/api/me"); } catch { S.me = null; }
  }
  $("logo").onclick = () => go("home");
  document.querySelectorAll("footer [data-go]").forEach(a => a.onclick = () =>
    a.dataset.go === "auth" ? go("auth", { mode: "signin" }) : go(a.dataset.go));
  const h = location.hash.slice(1);
  if (!S.me) return go(["privacy", "signin", "signup"].includes(h) ? (h === "privacy" ? "privacy" : "auth") : "home",
                       { mode: h === "signup" ? "signup" : "signin" });
  return go(homeView());
}

function setHash(h) { S.route = h; if (location.hash.slice(1) !== h) location.hash = h; }

// Back/forward buttons and links like /#signup or /#privacy
window.addEventListener("hashchange", () => {
  const h = location.hash.slice(1);
  if (h === S.route) return;
  if (h === "privacy") return go("privacy");
  if (h === "signin" || h === "signup") return go("auth", { mode: h });
  go(S.me ? homeView() : "home");
});

function go(view, opts = {}) {
  const main = $("main");
  main.classList.toggle("wide", view === "home");
  window.scrollTo(0, 0);
  if (view === "home") { setNav(S.me ? navFor(S.me) : [], ""); setHash(""); return renderHome(main); }
  if (view === "privacy") { setNav(S.me ? navFor(S.me) : [], ""); setHash("privacy"); return renderPrivacy(main); }
  if (view === "auth") {
    if (S.me) return go(homeView());
    setNav([], ""); setHash(opts.mode === "signup" ? "signup" : "signin");
    return renderAuth(main, opts);
  }
  if (!S.me) return go("auth", { mode: "signin", notice: "Please sign in to continue." });
  setHash("");
  if (S.me.role === "agent") {
    setNav(navFor(S.me), view);
    return ({ overview: renderOverview, users: renderUsers, audit: renderAudit, model: renderModel,
              metrics: renderMetrics, rules: renderRules }[view] || renderOverview)(main);
  }
  if (view === "questionnaire") { setNav(S.me.has_profile ? [["discover", "Discover"], ["matches", "My matches"], ["answers", "My answers"]] : [], "answers"); return renderQuestionnaire(main); }
  setNav(navFor(S.me), view);
  return ({ discover: renderDiscover, matches: renderMatches, answers: renderAnswers }[view] || renderDiscover)(main);
}

function navFor(me) {
  return me.role === "agent"
    ? [["overview", "Overview"], ["users", "Users"], ["audit", "Fairness audit"], ["model", "AI model"], ["metrics", "Launch metrics"], ["rules", "Rules demo"]]
    : [["discover", "Discover"], ["matches", "My matches"], ["answers", "My answers"]];
}

async function signOut() {
  try { await api("/api/auth/signout", {}); } catch {}
  signOutLocal();
}
function signOutLocal() { S.token = null; S.me = null; store.set(null); go("home"); }

// ================================================================ sign in / sign up
function renderAuth(main, opts = {}) {
  let mode = opts.mode || "signin", role = opts.role || "tenant";
  main.innerHTML = `<div class="auth panel">
    ${opts.notice ? `<div class="notice">${esc(opts.notice)}</div>` : ""}
    <div class="seg"><button data-m="signin">Sign in</button><button data-m="signup">Create account</button></div>
    <div id="roleBox" class="hidden">
      <label>First — who are you?</label>
      <div class="roles">
        <div class="role" data-r="tenant"><div class="em">🔑</div><b>I'm a Tenant</b><small>Looking for a home and a landlord that fit my life.</small></div>
        <div class="role" data-r="landlord"><div class="em">🏠</div><b>I'm a Landlord</b><small>Looking for a compatible, reliable tenant.</small></div>
      </div>
    </div>
    <label>Email</label><input id="email" type="email" autocomplete="email">
    <label>Password</label><input id="pw" type="password" autocomplete="current-password" placeholder="At least 8 characters">
    <div id="consentBox" class="hidden">
      <label class="check"><input type="checkbox" id="cAdult"> I'm 18 or older</label>
      <label class="check"><input type="checkbox" id="cPrivacy"> I've read and agree to the
        <a href="/#privacy" target="_blank" rel="noopener">Privacy Policy</a></label>
    </div>
    <div class="err" id="authErr"></div>
    <button class="btn" id="authBtn">Sign in</button>
    <div class="demo" id="demoInfo"></div>
  </div>`;
  const c = S.config || {};
  const list = (role) => (c.demo_accounts || []).filter(a => a.role === role).map(a => `<code>${esc(a.email)}</code>`).join(", ");
  $("demoInfo").innerHTML = `Demo accounts (password <code>${esc(c.demo_password || "demo1234")}</code>): tenants ${list("tenant")} ·
    landlords ${list("landlord")}${c.owner_hint ? ` · website owner <code>${esc(c.owner_hint.email)}</code> (<code>${esc(c.owner_hint.password)}</code>)` : ""}.
    Everyone starts with 10 free matches. The app is for adults 18+.`;
  const setMode = (m) => {
    mode = m;
    main.querySelectorAll(".seg button").forEach(x => x.classList.toggle("on", x.dataset.m === m));
    $("roleBox").classList.toggle("hidden", mode !== "signup");
    $("consentBox").classList.toggle("hidden", mode !== "signup");
    $("authBtn").textContent = mode === "signup" ? "Create account" : "Sign in";
    $("pw").autocomplete = mode === "signup" ? "new-password" : "current-password";
    $("authErr").textContent = "";
  };
  const setRole = (r) => { role = r; main.querySelectorAll(".role").forEach(x => x.classList.toggle("on", x.dataset.r === r)); };
  main.querySelectorAll(".seg button").forEach(b => b.onclick = () => setMode(b.dataset.m));
  main.querySelectorAll(".role").forEach(r => r.onclick = () => setRole(r.dataset.r));
  setMode(mode); setRole(role);
  const submit = async () => {
    const email = $("email").value.trim(), password = $("pw").value;
    $("authErr").textContent = "";
    if (!email || !password) return $("authErr").textContent = "Enter your email and password.";
    if (mode === "signup" && password.length < 8) return $("authErr").textContent = "Password must be at least 8 characters.";
    if (mode === "signup" && !($("cAdult").checked && $("cPrivacy").checked))
      return $("authErr").textContent = "Please confirm you're 18 or older and agree to the Privacy Policy.";
    $("authBtn").disabled = true;
    try {
      const r = await api(mode === "signup" ? "/api/auth/signup" : "/api/auth/signin",
        { email, password, role, adult: $("cAdult").checked, privacy: $("cPrivacy").checked });
      S.token = r.token; S.me = r.me; store.set(r.token);
      boot();
    } catch (e) { $("authErr").textContent = e.message; }
    $("authBtn").disabled = false;
  };
  $("authBtn").onclick = submit;
  $("pw").onkeydown = (e) => { if (e.key === "Enter") submit(); };
}

// ================================================================ public home (adapted from the front-end hand-off)
// Changes from the hand-off, to fit Deservia's own fairness rules: no "diet" in the copy, no
// "Vegetarian-friendly" tag, no "99% match accuracy" claim, FAQ describes what is really scored.
const PLANS = [
  { name: "Everyone", price: "$0", unit: "free forever", featured: false, soon: false,
    perks: ["Create a lifestyle profile", "10 free matches", "Swipe on matches", "Mutual-match alerts"] },
  { name: "Tenant Silver", price: "$9.99", unit: "/month", featured: true, soon: false,
    perks: ["Everything in Free", "Unlimited matches", "See who liked you", "Priority in match queue"] },
  { name: "Landlord Gold", price: "$29.99", unit: "/listing · 30 days", featured: false, soon: false,
    perks: ["Unlimited tenant matches", "Featured listing", "Match insights", "Shareable listing link"] },
  { name: "Landlord Platinum", price: "$49.99", unit: "/listing · 60 days", featured: false, soon: false,
    perks: ["Everything in Gold", "Top placement 60 days", "Tenant screening add-on", "Human stager referral"] },
];

function renderHome(main) {
  const signedIn = !!S.me;
  const cta = signedIn ? (S.me.role === "agent" ? "Open the owner console" : "Go to my matches") : "Find your match — free";
  main.innerHTML = `
  <section class="hero"><div class="wrap hero-grid">
    <div>
      <span class="pill">Like Bumble, but for landlords & tenants</span>
      <h1>Matching lifestyles,<br><b>not just leases.</b></h1>
      <p class="hero-sub">Deservia pairs landlords and tenants on how they actually live: sleep schedule, pets, noise,
        cleanliness, smoking and kitchen habits, so every rental starts compatible.</p>
      <div class="hero-cta">
        <button class="pbtn" id="heroGo">${cta}</button>
        <button class="gbtn" id="heroHow">See how it works</button>
      </div>
      <div class="stat-row">
        <div class="stat"><b>15</b><span>Lifestyle questions</span></div>
        <div class="stat"><b>0</b><span>Protected grounds used</span></div>
        <div class="stat"><b>Free</b><span>To get matched</span></div>
        <div class="stat"><b>1</b><span>Ontario lease, e-signed</span></div>
      </div>
    </div>
    <div class="listing-card">
      <div class="listing-photo">🏡<span class="match-badge">96% MATCH</span></div>
      <div class="listing-body">
        <strong>Maple Lane basement suite · Brampton</strong>
        <div class="note" style="font-size:14px">Basement apartment · $1,700/mo</div>
        <div class="chips"><span class="chip">Non-smoker</span><span class="chip">Quiet home</span>
          <span class="chip">Pet lover</span><span class="chip">Early riser</span></div>
        <div class="swipe-row">
          <button class="swipe-btn" data-match title="Pass">✕</button>
          <button class="swipe-btn" data-match title="Like">♥</button>
        </div>
      </div>
    </div>
  </div></section>

  <section class="block" id="how"><div class="wrap">
    <div class="eyebrow">How it works</div><h2>Four steps to a compatible home</h2>
    <div class="steps">${[["Tell us your lifestyle", "A quick questionnaire about how you live. Type your own answer anytime."],
      ["Get matched", "Our engine ranks the most compatible people and homes, and explains why."],
      ["Swipe & connect", "Swipe ♥ or ✕. When it's mutual, your agent books a viewing."],
      ["Screen & sign", "Screen with SingleKey and e-sign your Ontario Standard Lease."]].map(([t, p], i) =>
      `<div class="step"><div class="num">${i + 1}</div><h3>${t}</h3><p>${p}</p></div>`).join("")}</div>
  </div></section>

  <section class="block tint"><div class="wrap">
    <div class="eyebrow">Why it's different</div><h2>Compatibility, done fairly</h2>
    <div class="grid-3">${[["🤝", "Lifestyle compatibility", "Matched on habits, not just budget and location."],
      ["💡", "Explained matches", "Every match shows what you have in common."],
      ["🧠", "Learns what you like", "Your swipes make your next matches better."],
      ["📄", "Ontario Standard Lease", "Generated for e-signing once both sides agree."],
      ["🏠", "Every rental type", "Rooms, basements, apartments, upper floors, whole homes."],
      ["⚖️", "Fair by design", "We match on how you live, never on who you are."]].map(([i, h, p]) =>
      `<div class="feature"><div class="ico">${i}</div><h3>${h}</h3><p>${p}</p></div>`).join("")}</div>
  </div></section>

  <section class="block"><div class="wrap">
    <div class="eyebrow">Membership</div><h2>Start free, upgrade when ready</h2>
    <div class="plans">${PLANS.map(p => `<div class="plan ${p.featured ? "featured" : ""}">
        ${p.soon ? '<span class="tag-soon">Coming soon</span>' : ""}<h3>${p.name}</h3>
        <div class="price">${p.price} <small>${p.unit}</small></div>
        <ul>${p.perks.map(x => `<li>${x}</li>`).join("")}</ul>
        <button class="${p.price === "$0" ? "pbtn" : "gbtn"}" data-match>${p.price === "$0" ? "Get started free" : "Choose plan"}</button>
      </div>`).join("")}</div>
  </div></section>

  <section class="block tint"><div class="wrap">
    <div class="eyebrow">FAQ</div><h2>Questions & answers</h2>
    ${[["Is Deservia free to use?", "Yes. Creating a profile, getting matched and swiping are free. Paid tiers add visibility and screening tools."],
       ["How does matching work?", "We compare how you live: schedule, cleanliness, noise, pets, smoking, kitchen habits, repairs and budget, using what each side says matters most. Every match shows what you have in common."],
       ["What do you never match on?", "Age, family status, disability, religion, race, place of origin, citizenship, sex, sexual orientation, gender identity or receipt of public assistance. Preferences like these are kept out of every score."],
       ["Is my data private?", "Your profile is used only for matching, under Canada's PIPEDA. We never store card, bank or credit-report details. See our Privacy Policy."],
       ["How is the lease signed?", "After a mutual match, a viewing and SingleKey screening, Deservia generates an Ontario Standard Lease you can e-sign."],
       ["Who decides?", "Deservia suggests, never decides. The landlord chooses, and either side can walk away at any time."]].map(([q, a]) =>
      `<div class="qa-item"><button class="qa-q">${q}<span class="pm">+</span></button><div class="qa-a">${a}</div></div>`).join("")}
  </div></section>

  <section class="block"><div class="wrap" style="text-align:center">
    <h2>Ready to meet your match?</h2>
    <p class="note" style="font-size:16px;margin:-8px auto 20px">Join free and get matched on lifestyle in minutes. Adults 18+.</p>
    <button class="pbtn" data-match>Get started free →</button>
  </div></section>`;
  $("heroGo").onclick = () => startMatching();
  $("heroHow").onclick = () => $("how").scrollIntoView({ behavior: "smooth" });
  main.querySelectorAll("[data-match]").forEach(b => b.onclick = () => startMatching());
  main.querySelectorAll(".qa-q").forEach(b => b.onclick = () => b.parentNode.classList.toggle("open"));
}

function renderPrivacy(main) {
  // Summarised from Deservia's working-draft Privacy & Data Protection Policies (to be finalised by a lawyer).
  main.innerHTML = `<div class="legal">
    <a class="link" id="backHome" style="cursor:pointer;color:var(--pink);font-weight:700">← Home</a>
    <h2>Privacy Policy</h2>
    <p><em>Working draft, Deservia Realty Inc., Brampton, Ontario. Reflects PIPEDA and the Ontario Human Rights Code; to be reviewed by a lawyer before real users sign up.</em></p>
    ${[["What we collect", "Your email and login, your lifestyle questionnaire answers (routines, noise, tidiness, hobbies, pets, smoking, kitchen habits) and your home preferences or listing details. We do not collect or store card numbers, banking details, or credit or income screening reports."],
       ["What we never match on", "Age, family status, disability, religion, race, place of origin, citizenship, sex, sexual orientation, gender identity, or receipt of public assistance."],
       ["Adults only", "You must be 18 or older to create an account."],
       ["How we use it", "To create your profile, generate lifestyle-compatibility matches, and move a mutual match toward a viewing and a signed lease."],
       ["Third parties", "Stripe processes payments (we only receive a payment-status token). SingleKey handles tenant screening after a mutual match, with your consent; we show the result but do not store the report."],
       ["Sharing", "We do not sell your data. Your profile is shared with a match only after a compatibility score is generated and you choose to proceed."],
       ["Retention", "After a lease is signed, or after 90 days without activity, your data is archived or anonymized. You can ask for deletion at any time."],
       ["Your rights", "You may access, correct, withdraw consent, or request deletion of your information."],
       ["Automated decisions", "Some safety actions are automated and are only ever for conduct, never for who you are. You can ask for a free human review."],
       ["Contact", "deservia@gmail.com · 905-458-0444"]].map(([h, p]) => `<h3>${h}</h3><p>${p}</p>`).join("")}
  </div>`;
  $("backHome").onclick = () => go("home");
}

// ================================================================ questionnaire (one question per screen)
const Q = {};
async function renderQuestionnaire(main) {
  const defs = await api("/api/questions", { role: S.me.role });
  Q.defs = defs.questions; Q.areas = defs.areas; Q.answers = structuredClone(S.me.answers || {}); Q.i = 0; Q.main = main;
  drawQ();
}
const visibleQs = () => Q.defs.filter(q => Object.entries(q.show_if || {}).every(([k, v]) => Q.answers[k] === v));

function drawQ() {
  const qs = visibleQs(), q = qs[Q.i], n = qs.length, a = Q.answers[q.id];
  let body = "";
  const typed = Q.answers[q.id + "_other"];
  const otherOpen = Q.other === q.id || (typed && typed.length);
  if (q.type === "single") {
    body = q.options.map((o, k) => `<button class="opt ${a === o.v && !otherOpen ? "on" : ""}" data-k="${k}"><span class="ic">${o.icon}</span>${esc(o.label)}${a === o.v && !otherOpen ? '<span class="ck">✓</span>' : ""}</button>`).join("") +
      `<button class="opt ${otherOpen ? "on" : ""}" id="qOther"><span class="ic">✏️</span>Other: type your own${otherOpen ? '<span class="ck">✓</span>' : ""}</button>` +
      (otherOpen ? `<input id="qOtherIn" maxlength="80" placeholder="Type your answer" value="${esc(typed || "")}">
        <div class="note">If it clearly matches an option we'll use it for matching; otherwise it's shown on your profile.</div>
        <div class="err" id="qErr"></div><button class="btn" id="qNext">Continue →</button>` : "");
  } else if (q.type === "multi") {
    const sel = a || [];
    body = q.options.map((o, k) => `<button class="opt ${sel.includes(o.v) ? "on" : ""}" data-k="${k}"><span class="ic">${o.icon}</span>${esc(o.label)}${sel.includes(o.v) ? '<span class="ck">✓</span>' : ""}</button>`).join("") +
      `<label>✏️ Add your own (separate with commas)</label>
       <input id="qOtherIn" maxlength="150" placeholder="e.g. pickleball, chess, hiking" value="${esc((typed || []).join(", "))}">
       <div class="err" id="qErr"></div><button class="btn" id="qNext">Continue →</button>`;
  } else if (q.type === "number") {
    body = `<input id="qIn" type="number" inputmode="numeric" min="${q.min}" max="${q.max}" placeholder="${esc(q.placeholder || "")}" value="${a ?? ""}">
      <div class="err" id="qErr"></div><button class="btn" id="qNext">Continue →</button>`;
  } else if (q.type === "area") {
    body = `<input id="qIn" list="areaList" maxlength="80" placeholder="Pick from the list or type your area" value="${esc(a || "")}">
      <datalist id="areaList">${Object.values(Q.areas).flat().map(x => `<option value="${esc(x)}">`).join("")}</datalist>
      <div class="note">Start typing to see suggestions, or type any city or neighbourhood.</div>
      <div class="err" id="qErr"></div><button class="btn" id="qNext">Continue →</button>`;
  } else if (q.type === "text") {
    body = `<textarea id="qIn" placeholder="${esc(q.placeholder || "")}">${esc(a || "")}</textarea>
      ${q.check_text ? `<div id="qCheck" class="chips"></div><div class="note">Phrases about who someone is (age, family, religion, origin, income source…) are struck out and never used.</div>` : ""}
      <div class="err" id="qErr"></div><button class="btn" id="qNext">Continue →</button>`;
  }
  const last = Q.i === n - 1;
  Q.main.innerHTML = `<div class="q">
    <button class="back" id="qBack">← ${Q.i === 0 ? (S.me.has_profile ? "Cancel" : "Sign out") : "Back"}</button>
    <div class="progress"><i style="width:${Math.round((Q.i + 1) / n * 100)}%"></i></div>
    <div class="count">Question ${Q.i + 1} of ${n}</div>
    <h2>${esc(q.title)}</h2>${q.sub ? `<div class="sub">${esc(q.sub)}</div>` : '<div class="sub"></div>'}
    ${body}</div>`;
  if (last && $("qNext")) $("qNext").textContent = "Save my answers";
  $("qBack").onclick = () => Q.i === 0 ? (S.me.has_profile ? go("answers") : signOut()) : (Q.i--, Q.other = null, drawQ());

  if (q.type === "single") {
    $("qOther").onclick = () => { Q.other = q.id; drawQ(); $("qOtherIn").focus(); };
    if ($("qOtherIn")) {
      $("qOtherIn").onkeydown = (e) => { if (e.key === "Enter") next(); };
      $("qNext").onclick = next;
    }
    Q.main.querySelectorAll(".opt[data-k]").forEach(b => b.onclick = () => {
      Q.other = null; delete Q.answers[q.id + "_other"];
      Q.answers[q.id] = q.options[+b.dataset.k].v;
      // answers that hide follow-up questions (e.g. pet kind) are cleared when they no longer apply
      Q.defs.forEach(d => { if (d.show_if && !Object.entries(d.show_if).every(([k, v]) => Q.answers[k] === v)) delete Q.answers[d.id]; });
      drawQ(); setTimeout(next, 220);
    });
  } else if (q.type === "multi") {
    Q.main.querySelectorAll(".opt").forEach(b => b.onclick = () => {
      Q.answers[q.id + "_other"] = splitList($("qOtherIn").value);
      const v = q.options[+b.dataset.k].v, sel = new Set(Q.answers[q.id] || []);
      sel.has(v) ? sel.delete(v) : sel.add(v);
      Q.answers[q.id] = [...sel]; drawQ();
    });
    $("qNext").onclick = next;
  } else if (["number", "area", "text"].includes(q.type)) {
    if (q.check_text) {
      let t; const check = () => { clearTimeout(t); t = setTimeout(async () => {
        if (!$("qIn")) return;                      // user already moved to the next question
        const r = await api("/api/check-text", { text: $("qIn").value }).catch(() => null);
        if (r && $("qCheck")) $("qCheck").innerHTML = r.kept.map(k => `<span class="chip ok">${esc(k)}</span>`).join("") +
          r.excluded.map(e => `<span class="chip no">${esc(e.text)}</span><span class="chip flag">not used: ${esc(e.ground)}</span>`).join("");
      }, 250); };
      $("qIn").oninput = check; check();
    }
    $("qIn").focus();
    $("qIn").onkeydown = (e) => { if (e.key === "Enter" && q.type !== "text") next(); };
    $("qNext").onclick = next;
  }

  async function next() {
    const otherIn = $("qOtherIn");
    if (otherIn) {
      const raw = otherIn.value.trim();
      $("qErr").textContent = "";
      if (q.type === "single" && !raw) return $("qErr").textContent = "Type your answer, or pick one of the options above.";
      const items = q.type === "multi" ? splitList(raw) : (raw ? [raw] : []);
      for (const it of items) {
        const r = await api("/api/check-text", { text: it }).catch(() => ({ excluded: [] }));
        if (r.excluded.length) return $("qErr").textContent =
          `"${r.excluded[0].text}" describes who someone is (${r.excluded[0].ground}), not how they live. Please rephrase.`;
      }
      if (q.type === "single") { Q.answers[q.id + "_other"] = raw; delete Q.answers[q.id]; Q.other = null; }
      else { if (items.length) Q.answers[q.id + "_other"] = items; else delete Q.answers[q.id + "_other"]; }
    }
    if (["number", "area", "text"].includes(q.type)) {
      const v = $("qIn").value.trim();
      $("qErr").textContent = "";
      if (q.type === "number") {
        const num = Number(v);
        if (!v || isNaN(num) || num < q.min || num > q.max) return $("qErr").textContent = `Enter a number between ${q.min} and ${q.max}.`;
        Q.answers[q.id] = Math.round(num);
      } else if (q.type === "area") {
        if (!v) return $("qErr").textContent = "Pick or type an area.";
        Q.answers[q.id] = v;
      } else {
        if (v) Q.answers[q.id] = v; else delete Q.answers[q.id];
      }
    }
    if (Q.i < visibleQs().length - 1) { Q.i++; Q.other = null; drawQ(); } else save();
  }
}

function splitList(s) { return String(s || "").split(",").map(x => x.trim()).filter(Boolean).slice(0, 5); }

async function save() {
  try {
    const first = !S.me.has_profile;
    S.me = await api("/api/me/answers", { answers: Q.answers });
    clearRound();
    toast(first ? "Welcome to Deservia! Here are your first 10 matches." : "Saved! Finding your matches…");
    go("discover");
  } catch (e) {
    if ($("qErr")) $("qErr").textContent = e.message; else toast(e.message);
  }
}

async function renderAnswers(main) {
  try { S.me = await api("/api/me"); } catch {}
  const rows = S.me.answers_view || [];
  main.innerHTML = `<div class="panel" style="max-width:720px;margin:0 auto">
    <h2>My answers</h2>
    <div class="note" style="margin-bottom:8px">Everything you told us, including anything you typed yourself.</div>
    <table>${rows.map(r => `<tr><th style="width:38%">${esc(r.question)}</th><td>
        ${r.answer ? `<div>${esc(r.answer)}</div>` : ""}
        ${r.typed ? `<div class="typed">✏️ “${esc(r.typed)}”</div>` : ""}
        ${r.used ? `<div class="note">${esc(r.used)}</div>` : ""}</td></tr>`).join("")}</table>
    <button class="btn" id="edit">Edit my answers</button>
    <h2 style="margin-top:26px">My plan</h2>
    <p>${S.me.usage?.unlimited ? `<b>${esc(S.me.usage.plan_name)}</b>, unlimited matches.`
       : `<b>Free</b>, ${Math.min(S.me.usage?.used ?? 0, S.me.usage?.free_limit ?? 10)} of ${S.me.usage?.free_limit ?? 10} free matches used.`}</p>
    <button class="btn ghost" id="planBtn">${S.me.usage?.unlimited ? "Cancel subscription (demo)" : "See membership plans"}</button>
    <h2 style="margin-top:26px">Delete my account</h2>
    <p class="note">Permanently deletes your account, your answers, your swipes and your matches. This can't be undone.</p>
    <button class="btn danger" id="delOpen">Delete my account</button>
    <div id="delBox" class="hidden">
      <label>Enter your password to confirm</label><input id="delPw" type="password" autocomplete="current-password">
      <div class="err" id="delErr"></div>
      <button class="btn danger" id="delGo">Permanently delete my account</button>
      <button class="btn ghost" id="delCancel">Cancel</button>
    </div></div>`;
  $("edit").onclick = () => go("questionnaire");
  $("delOpen").onclick = () => { $("delBox").classList.remove("hidden"); $("delOpen").classList.add("hidden"); $("delPw").focus(); };
  $("delCancel").onclick = () => { $("delBox").classList.add("hidden"); $("delOpen").classList.remove("hidden"); };
  $("delGo").onclick = async () => {
    $("delErr").textContent = "";
    if (!$("delPw").value) return $("delErr").textContent = "Enter your password.";
    $("delGo").disabled = true;
    try {
      await api("/api/me/delete", { password: $("delPw").value });
      clearRound(); signOutLocal();
      toast("Your account and data have been deleted.");
    } catch (e) { $("delErr").textContent = e.message; $("delGo").disabled = false; }
  };
  $("planBtn").onclick = async () => {
    if (S.me.usage?.unlimited) { S.me = await api("/api/unsubscribe", {}); toast("Back on the free plan."); renderAnswers(main); }
    else openPlans();
  };
}

// ================================================================ discover (swipe)
let D = { deck: [], i: 0, results: [], likes: [], swipes: null };

// The current round of 10 is kept per user in the browser, so leaving Discover (or refreshing the
// page) never replaces it. Only "Show my next 10" fetches a new round.
const roundKey = () => "deservia_round_" + (S.me?.email || "");
function saveRound() { try { const { busy, ...keep } = D; localStorage.setItem(roundKey(), JSON.stringify(keep)); } catch {} }
function loadRound() { try { return JSON.parse(localStorage.getItem(roundKey()) || "null"); } catch { return null; } }
function clearRound() { try { localStorage.removeItem(roundKey()); } catch {} }

function drawSide() {
  $("likes").innerHTML = (D.likes || []).length ? D.likes.map(x => `<span class="chip learned">${esc(x)}</span>`).join("")
    : `<span class="note">Swipe a few to find out.</span>`;
  if (D.swipes) $("mySwipes").textContent = `${D.swipes.swipes} so far (${D.swipes.likes} ♥ · ${D.swipes.passes} ✕)`;
  const u = D.usage || S.me.usage;
  if (u && $("myPlan")) $("myPlan").innerHTML = u.unlimited ? `${esc(u.plan_name)} · unlimited matches`
    : `Free · ${Math.min(u.used, u.free_limit)} of ${u.free_limit} free matches used <a class="link" id="seePlans" style="color:var(--pink);cursor:pointer">See plans</a>`;
  if ($("seePlans")) $("seePlans").onclick = () => openPlans();
}

// ---------------- membership: shown when the free matches are used up ----------------
async function openPlans(payload) {
  const data = payload && payload.plans ? payload : await api("/api/plans");
  const u = data.usage || {};
  const ov = document.createElement("div");
  ov.className = "overlay"; ov.id = "plansOverlay";
  ov.innerHTML = `<div class="modal">
    <button class="x" id="plansClose" title="Close">✕</button>
    <div class="eyebrow">Membership</div>
    <h2>${u.unlimited ? "Your membership" : `You've used your ${u.free_limit ?? 10} free matches`}</h2>
    <p class="note" style="font-size:14px">${u.unlimited ? "You can change your plan anytime." :
      "Subscribe to keep matching. Your likes and mutual matches so far are saved either way."}</p>
    <div class="plans modal-plans">${data.plans.map(p => {
      const current = p.id === (u.plan || "free");
      return `<div class="plan ${p.id !== "free" ? "featured" : ""}">
        <h3>${esc(p.name)}</h3><div class="price">${esc(p.price)} <small>${esc(p.unit)}</small></div>
        <ul>${p.perks.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
        ${current ? `<button class="gbtn" disabled>Current plan</button>`
          : p.id === "free" ? `<button class="gbtn" disabled>Free plan</button>`
          : `<button class="pbtn" data-plan="${esc(p.id)}">Subscribe</button>`}
      </div>`; }).join("")}</div>
    <div class="note demo-pay">🧪 Demo checkout: no card is asked for and no payment is taken. Real payments will go through Stripe.</div>
    <button class="btn ghost" id="plansLater">Maybe later</button>
  </div>`;
  document.body.appendChild(ov);
  const close = () => ov.remove();
  $("plansClose").onclick = close; $("plansLater").onclick = close;
  ov.onclick = (e) => { if (e.target === ov) close(); };
  ov.querySelectorAll("[data-plan]").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Subscribing…";
    try {
      S.me = await api("/api/subscribe", { plan: b.dataset.plan });
      close();
      toast(`You're on ${S.me.usage.plan_name} (demo, no payment). Enjoy unlimited matches!`);
      if ($("flash")) loadDeck(); else go(homeView());
    } catch (e) { b.disabled = false; b.textContent = "Subscribe"; toast(e.message); }
  });
}

function cardHTML(c) {
  const excl = c.excluded?.length ? `<div class="shield"><b>🛡 Not used for matching</b>${
      c.excluded.map(e => `“${esc(e.text)}” touches <i>${esc(e.ground)}</i>`).join("<br>")}</div>` : "";
  const price = c.price ? `$${Number(c.price).toLocaleString()}${c.price_label === "budget" ? " budget" : "/mo"}` : "";
  const extra = (c.ml_success_pct != null ? `<div class="note">🤖 AI ${c.ml_success_pct}% smooth tenancy · rank ${c.rank_score ?? ""}</div>` : "");
  return `<div class="row">
      <div class="icon">${S.me?.role === "landlord" ? "🙂" : (ICON[c.rental_type] || "🏠")}</div>
      <div><div class="title">${esc(c.name)}</div><div class="sub2">${esc(c.rental_type)} · ${esc(c.area)}</div></div>
      <div class="pct"><b style="color:${pctColor(c.match_pct)}">${c.match_pct}%</b><small>MATCH</small></div>
    </div>${extra}
    <div class="price">${price}</div>
    <div class="desc">${esc(c.description)}</div>
    <div class="chips">${(c.tags || []).map(t => `<span class="chip">${esc(t)}</span>`).join("")}${(c.flags || []).map(f => `<span class="chip flag">⚠ ${esc(f)}</span>`).join("")}</div>
    <div class="common">💚 ${c.in_common_count} things in common</div>
    <div class="chips">${(c.in_common || []).map(x => `<span class="chip ok">${esc(x)}</span>`).join("")}</div>
    ${excl}${(c.notes || []).map(n => `<div class="note">ℹ ${esc(n)}</div>`).join("")}`;
}

function renderDiscover(main) {
  // One centred column: heading, progress dots, the flashcard, ♥/✕, then a small info panel.
  main.innerHTML = `<div class="discover">
    <h2 class="disc-title">${S.me.role === "tenant" ? "Homes that fit your life" : "Tenants who fit your home"}</h2>
    <div class="note disc-sub">Swipe ♥ to like, ✕ to pass. Your best matches come first, and they get better as you swipe.</div>
    <div class="dots" id="dots"></div>
    <div id="flash" class="flash"></div>
    <div class="actions" id="actions" style="visibility:hidden">
      <button class="round no" id="nope" title="Pass (←)">✕</button><button class="round yes" id="like" title="Like (→)">♥</button>
    </div>
    <div class="note" style="margin-top:8px">Keyboard: ← pass · → like</div>
    <div class="disc-info">
      <div><b>We've noticed you like</b><div id="likes" class="chips"><span class="note">Swipe a few to find out.</span></div></div>
      <div><b>Your swipes</b><div id="mySwipes" class="note">–</div></div>
      <div><b>Your plan</b><div id="myPlan" class="note">–</div></div>
    </div>
    <div class="note disc-fair">We match on how you live, never on who you are. Deservia suggests; ${S.me.role === "tenant" ? "the landlord decides" : "you decide"}.</div>
  </div>`;
  $("like").onclick = () => swipe(true);
  $("nope").onclick = () => swipe(false);
  const saved = loadRound();
  if (saved && saved.deck && saved.deck.length) { D = saved; drawSide(); showCard(); }
  else loadDeck();
}

async function loadDeck() {
  $("flash").innerHTML = `<p class="note"><span class="spin">⚙️</span> Finding your best matches…</p>`;
  try {
    const d = await api("/api/deck", {});
    D = { deck: d.cards, i: 0, results: [], likes: d.you_seem_to_like, swipes: d.swipes, usage: d.usage };
    drawSide();
    if (!D.deck.length) { clearRound(); $("flash").innerHTML = `<p>You've seen all your matches for now. Check back soon!</p>`; return; }
    saveRound();
    showCard();
  } catch (e) {
    if (e.status === 402) {
      S.me.usage = e.data.usage; D.usage = e.data.usage; drawSide();
      $("actions").style.visibility = "hidden";
      $("flash").innerHTML = `<h2 style="color:var(--navy);margin-top:0">You've used your ${e.data.usage.free_limit} free matches</h2>
        <p>Choose a plan to see your next matches. Your likes and mutual matches are saved.</p>
        <button class="btn" id="choosePlan">See membership plans</button>
        <button class="btn ghost" id="seeMatches2">See my matches</button>`;
      $("choosePlan").onclick = () => openPlans(e.data);
      $("seeMatches2").onclick = () => go("matches");
      return openPlans(e.data);
    }
    $("flash").innerHTML = `<p class="err">${esc(e.message)}</p>`;
  }
}

function showCard() {
  $("dots").innerHTML = D.deck.map((_, k) => `<i class="${D.results[k] === true ? "like" : D.results[k] === false ? "pass" : k === D.i ? "now" : ""}"></i>`).join("");
  const f = $("flash"); f.className = "flash";
  if (D.i < D.deck.length) { f.innerHTML = cardHTML(D.deck[D.i]); $("actions").style.visibility = "visible"; return; }
  $("actions").style.visibility = "hidden";
  const likes = D.results.filter(Boolean).length;
  f.innerHTML = `<h2 style="color:var(--navy);margin-top:0">That's your 10 for now</h2>
    <p>You liked <b>${likes}</b> of ${D.deck.length}. We're learning from your swipes to make your next matches even better.</p>
    ${D.usage && !D.usage.unlimited && D.usage.used >= D.usage.free_limit ? `<p class="note">That was your ${D.usage.free_limit} free matches. The next 10 need a membership.</p>` : ""}
    <button class="btn" id="more">Show my next 10</button>
    <button class="btn ghost" id="seeMatches">See my matches</button>`;
  $("more").onclick = loadDeck;
  $("seeMatches").onclick = () => go("matches");
}

async function swipe(liked) {
  if (D.i >= D.deck.length || D.busy) return;
  D.busy = true;
  const c = D.deck[D.i];
  $("flash").classList.add(liked ? "out-right" : "out-left");
  D.results[D.i] = liked;
  D.i++;
  saveRound();                                   // progress survives leaving the page
  api("/api/swipe", { item_id: c.item_id, liked }).then(r => {
    if (r.mutual) toast("🎉 It's a mutual match! Your agent will reach out to book a viewing.");
    D.swipes = r.swipes; D.usage = r.usage; saveRound();
    if ($("mySwipes")) drawSide();
  }).catch(e => { if (e.status === 402) openPlans(e.data); else toast(e.message); });
  await new Promise(r => setTimeout(r, 330));
  D.busy = false;
  if ($("flash")) showCard();
}
document.addEventListener("keydown", e => {
  if (!$("flash") || ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  if (e.key === "ArrowRight") swipe(true);
  if (e.key === "ArrowLeft") swipe(false);
});

async function renderMatches(main) {
  main.innerHTML = `<div class="panel" style="max-width:680px;margin:0 auto"><h2>My matches</h2>
    <div class="note" style="margin-bottom:6px">You can withdraw a like at any time. A withdrawn mutual match is no longer mutual.</div>
    <div id="list" class="note">Loading…</div></div>`;
  const r = await api("/api/my-matches");
  $("list").innerHTML = r.matches.length ? r.matches.map(m => `<div class="matchrow ${m.mutual ? "mutual" : ""}">
      <div class="icon">${m.mutual ? "🎉" : "♥"}</div>
      <div><div class="title">${esc(m.name)}</div><div class="sub2">${esc(m.sub)}</div><div class="note">${esc(m.status)}</div></div>
      <div class="pct"><b style="color:${pctColor(m.match_pct)}">${m.match_pct}%</b><small>MATCH</small>
        <button class="wd" data-item="${esc(m.item_id)}" title="Withdraw your like">Withdraw</button></div></div>`).join("")
    : "No likes yet. Head to Discover and start swiping.";
  $("list").querySelectorAll(".wd").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try { await api("/api/withdraw", { item_id: b.dataset.item }); toast("Withdrawn. They won't see this match anymore."); renderMatches(main); }
    catch (e) { b.disabled = false; toast(e.message); }
  });
}

// ================================================================ agent console
async function renderOverview(main) {
  main.innerHTML = `<p class="note"><span class="spin">⚙️</span> Loading analysis…</p>`;
  const o = await api("/api/agent/overview"), k = o.kpis, lv = o.liked_vs_passed, m = o.model;
  const maxRate = Math.max(0.01, ...o.like_rate_by_match.map(b => b.like_rate));
  main.innerHTML = `
    <div class="kpis">
      ${[["Tenants", k.tenants], ["Landlords", k.landlords], ["Questionnaires done", k.profiles_done], ["Swipes", k.swipes],
         ["Like rate", k.like_rate == null ? "–" : Math.round(k.like_rate * 100) + "%"], ["Mutual matches", k.mutual_matches], ["Paid members", k.paid_members],
         ["AI model", "v" + (m.live_model_version ?? "–")]].map(([l, v]) => `<div class="kpi"><small>${l}</small><b>${v}</b></div>`).join("")}
    </div>
    <div class="two">
      <div class="panel"><h2>Do higher match scores get more likes?</h2>
        ${o.like_rate_by_match.length ? o.like_rate_by_match.map(b => `<div class="crit"><span>${b.bucket}</span><div class="bar"><i style="width:${b.like_rate / maxRate * 100}%"></i></div><span>${Math.round(b.like_rate * 100)}% (${b.swipes})</span></div>`).join("")
          : '<p class="note">No swipes yet.</p>'}
        <p class="note">If matching works, the like rate rises with the match %.</p></div>
      <div class="panel"><h2>Liked vs passed</h2><table>
        <tr><th></th><th>Liked</th><th>Passed</th></tr>
        <tr><td>Average match %</td><td><b>${lv.avg_match_liked ?? "–"}</b></td><td>${lv.avg_match_passed ?? "–"}</td></tr>
        <tr><td>Average AI smooth-tenancy %</td><td><b>${lv.avg_ai_liked ?? "–"}</b></td><td>${lv.avg_ai_passed ?? "–"}</td></tr>
        <tr><td>Tenant swipes</td><td colspan="2">${o.by_role.tenant.swipes} (${o.by_role.tenant.likes} ♥)</td></tr>
        <tr><td>Landlord swipes</td><td colspan="2">${o.by_role.landlord.swipes} (${o.by_role.landlord.likes} ♥)</td></tr></table></div>
      <div class="panel"><h2>Mutual matches (ready for a viewing)</h2>
        ${o.mutual.length ? `<table><tr><th>Tenant</th><th>Landlord</th><th>Home</th><th>Match</th></tr>${o.mutual.map(x =>
          `<tr><td>${esc(x.tenant)}</td><td>${esc(x.landlord)}</td><td>${esc(x.home)}</td><td>${x.match_pct}%</td></tr>`).join("")}</table>`
          : '<p class="note">None yet. A mutual match happens when a tenant and a landlord both swipe ♥ on each other.</p>'}</div>
      <div class="panel"><h2>AI model</h2>
        <p>Live model <b>v${m.live_model_version ?? "–"}</b>, trained with <b>${m.feedback_in_live_model ?? 0}</b> swipes.
           ${m.state === "training" ? '<span class="spin">⚙️</span> retraining…' : esc(m.message || "")}</p>
        ${m.fairness ? `<p class="note">Last retrain: held-out AUC ${m.auc_held_out ?? "–"} · fairness ratio ${m.fairness.disparate_impact_ratio} ${m.fairness.passes_four_fifths_rule ? "✓" : "✗"}</p>` : ""}
        <p class="note">Retrains automatically after every 10 swipes per user. Swipes join the shared model once there are 50+ (each person's taste is learned right away). A retrained model that fails the four-fifths fairness rule is rejected. "Reset all swipes" also restores the baseline model.</p>
        <button class="btn" id="retrain">Retrain now</button><button class="btn ghost" id="resetAll">Reset all swipes</button></div>
      <div class="panel" style="grid-column:1/-1"><h2>🛡 Protected-ground phrases written by users (kept out of every score)</h2>
        ${o.flagged_text.length ? `<table><tr><th>User</th><th>Role</th><th>Phrase</th><th>Ground</th></tr>${o.flagged_text.map(f =>
          `<tr><td>${esc(f.email)}</td><td>${esc(f.role)}</td><td>“${esc(f.text)}”</td><td>${esc(f.ground)}</td></tr>`).join("")}</table>
          <p class="note">These never affect matching. Consider a friendly note to the user about Deservia's fair-matching rules.</p>`
          : '<p class="note">None.</p>'}</div>
    </div>`;
  $("retrain").onclick = async () => { await api("/api/retrain", {}); toast("Retraining started"); setTimeout(() => go("overview"), 13000); };
  $("resetAll").onclick = async () => { if (confirm("Delete every swipe from every user?")) { await api("/api/feedback/reset", {}); go("overview"); } };
}

async function renderUsers(main) {
  const o = await api("/api/agent/overview");
  main.innerHTML = `<div class="panel"><h2>Users</h2><table>
    <tr><th>Email</th><th>Role</th><th>Plan</th><th>Questionnaire</th><th>Swipes</th><th>♥</th><th>Mutual</th><th>Learned preferences</th></tr>
    ${o.users.map(u => `<tr><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${u.plan === "free" ? "Free" : `<span class="badge">${esc(u.plan.replace("_", " "))}</span>`}</td><td>${u.profile_done ? "✓" : "–"}</td><td>${u.swipes}</td>
      <td>${u.likes}</td><td>${u.mutual_matches}</td><td>${u.learned.map(x => `<span class="chip learned">${esc(x)}</span>`).join(" ") || '<span class="note">–</span>'}</td></tr>`).join("")}
  </table></div>`;
}

async function renderAudit(main) {
  main.innerHTML = `<p class="note"><span class="spin">⚙️</span> Running the audit…</p>`;
  const a = await api("/api/admin/audit");
  main.innerHTML = `<div class="panel" style="margin-bottom:18px"><h2>Do scores differ by a protected group the engine never sees?</h2>
    <p class="note" style="font-size:14px">600 made-up tenants and 100 made-up listings. Each person has a hidden group the scorer can't read; group B is more
    likely to be vegetarian, work from home or be a student, the way these answers correlate with creed, disability, family status or age in real life.
    Four-fifths rule: each group's average good fits (≥80%) in its top 10 must be at least 80% of the best group's.</p></div>
    <div class="two">${["safe", "unsafe"].map(mode => {
      const x = a[mode], max = Math.max(...Object.values(x.groups).map(g => g.avg_good_fits_in_top10));
      return `<div class="panel"><h2>${mode === "safe" ? "Deservia engine (lifestyle only)" : "If we also scored diet, work-from-home and work"}</h2>
        <div class="big ${x.passes_four_fifths_rule ? "pass" : "fail"}">${x.disparate_impact_ratio} ${x.passes_four_fifths_rule ? "✓ passes" : "✗ fails"}</div>
        <div class="note">disparate impact ratio (needs ≥ 0.8)</div>
        ${Object.entries(x.groups).map(([g, v]) => `<label>Group ${g}: ${v.avg_good_fits_in_top10} good fits per top 10</label>
          <div class="bar"><i style="width:${v.avg_good_fits_in_top10 / max * 100}%"></i></div>`).join("")}</div>`; }).join("")}</div>`;
}

async function renderModel(main) {
  const c = await api("/api/admin/model");
  if (c.detail) { main.innerHTML = `<div class="panel">${esc(c.detail)}</div>`; return; }
  const R = c.results, F = c.fairness, mx = Math.max(...c.top_features.map(f => f.auc_drop));
  const rows = [["Random order", null, R.random_ranking_precision_at_k], ["Rule score only", R.rule_score_only.auc, R.rule_score_only.precision_at_k],
    ["Logistic regression", R.logistic_regression.auc, R.logistic_regression.precision_at_k], ["Gradient boosting (used)", R.gradient_boosting.auc, R.gradient_boosting.precision_at_k]];
  main.innerHTML = `<div class="two">
    <div class="panel"><h2>Does the AI pick better homes than the rules alone?</h2><table>
      <tr><th>Ranking</th><th>AUC</th><th>Smooth tenancies in top ${c.k}</th></tr>
      ${rows.map(([n, a, p]) => `<tr><td>${n}</td><td>${a ?? "–"}</td><td><b>${Math.round(p * 100)}%</b></td></tr>`).join("")}</table>
      <p class="note">Trained on ${c.pairs.toLocaleString()} past tenancies from <code>${esc(c.dataset.source)}</code>. Tested on ${esc(c.evaluation)}.
      Live model: v${c.version}${c.last_retrain ? ` (last retrain with ${c.last_retrain.feedback_rows} swipes, AUC ${c.last_retrain.auc_held_out})` : ""}.</p></div>
    <div class="panel"><h2>What the model learned matters most</h2>
      ${c.top_features.slice(0, 10).map(f => `<div class="crit" style="grid-template-columns:170px 1fr 56px"><span>${esc(f.feature)}</span><div class="bar"><i style="width:${Math.max(0, f.auc_drop) / mx * 100}%"></i></div><span>${f.auc_drop}</span></div>`).join("")}</div>
    <div class="panel"><h2>Fairness of the model</h2><table>
      <tr><td>Can the features guess the hidden group?</td><td><b>AUC ${F.group_leakage_auc}</b> (0.5 = no)</td></tr>
      <tr><td>Good fits per top ${c.k}, group A / B</td><td><b>${F.avg_good_fits_top_k.A} / ${F.avg_good_fits_top_k.B}</b></td></tr>
      <tr><td>Disparate impact ratio</td><td><b class="${F.passes_four_fifths_rule ? "pass" : "fail"}">${F.disparate_impact_ratio} ${F.passes_four_fifths_rule ? "✓" : "✗"}</b></td></tr></table></div>
    <div class="panel"><h2>Model card</h2><div class="note" style="font-size:13px">${["model", "predicts", "inputs", "training_data", "use"].map(k => `<p><b>${k.replace("_", " ")}:</b> ${esc(c[k])}</p>`).join("")}</div></div>
  </div>`;
}

async function renderMetrics(main) {
  const m = await api("/api/admin/metrics");
  const h = m.score_histogram_top10, hm = Math.max(...Object.values(h));
  main.innerHTML = `<div class="two">
    <div class="panel"><h2>Is matching performing? (dataset sample)</h2><table>
      <tr><td>Tenants / listings</td><td><b>${m.tenants} / ${m.listings}</b></td></tr>
      <tr><td>Tenants with ≥1 good fit in top 10</td><td><b>${Math.round(m.share_with_1_to_3_plus_good_fits_in_top10 * 100)}%</b></td></tr>
      <tr><td>Average good fits in top 10</td><td><b>${m.avg_good_fits_in_top10}</b></td></tr>
      <tr><td>Average best match</td><td><b>${m.avg_best_match}%</b></td></tr></table><p class="note">Target: ${esc(m.target)}</p></div>
    <div class="panel"><h2>Top-10 score distribution</h2>${Object.entries(h).map(([k, v]) =>
      `<div class="crit"><span>${k}%</span><div class="bar"><i style="width:${v / hm * 100}%"></i></div><span>${v}</span></div>`).join("")}</div>
    <div class="panel"><h2>Fairness filter fired (by ground)</h2>${Object.entries(m.text_filter_fired_by_ground).map(([g, n]) =>
      `<div class="crit" style="grid-template-columns:1fr 40px"><span>${esc(g)}</span><b>${n}</b></div>`).join("") || "None"}</div>
    <div class="panel"><h2>Never asked or never scored</h2>${Object.entries(m.not_scored_fields).map(([f, why]) =>
      `<p><b>${esc(f)}</b>: <span class="note">${esc(why)}</span></p>`).join("")}</div></div>`;
}

async function renderRules(main) {
  const tenants = await api("/api/tenants");
  main.innerHTML = `<div class="grid"><div class="panel"><h2>Rules demo</h2>
      <div class="note">One made-up tenant against 10 made-up listings, with a protected-ground preference kept out of the score (Sunday demo).</div>
      <label>Tenant</label><select id="rt">${tenants.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join("")}</select>
      <label>Ideal landlord (try adding "no kids")</label><textarea id="ri"></textarea>
      <button class="btn" id="rgo">Rank 10 listings</button></div>
    <div><div id="rsum" class="panel" style="margin-bottom:14px"></div><div id="rcards"></div></div></div>`;
  const fill = () => { $("ri").value = tenants.find(t => t.id === $("rt").value).profile.ideal_text || ""; };
  const run = async () => {
    const t = structuredClone(tenants.find(x => x.id === $("rt").value).profile);
    t.ideal_text = $("ri").value;
    const r = await api("/api/match", { tenant: t, limit: 10 });
    $("rsum").innerHTML = `<b>${r.good_fits_in_top} good fits (≥80%)</b> · ranked by ${esc(r.ranked_by)}`;
    $("rcards").innerHTML = r.matches.map(m => `<div class="card">${cardHTML({ ...m, excluded: m.excluded.map(e => ({ ...e, text: e.text + " (" + e.from + ")" })) })}</div>`).join("");
  };
  $("rt").onchange = () => { fill(); run(); };
  $("rgo").onclick = run;
  fill(); run();
}

boot();
