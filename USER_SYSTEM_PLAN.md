# Stock Matrix — User System & Matrix AI Credits Design Plan

> Status: **Design / RFC** — payment integration intentionally stubbed.
> Goal: evolve the current register/login-only auth into a tiered user system
> (anonymous → base → premium) with a credits-based AI economy and a referral
> growth loop, wired end-to-end into existing features (Monitor List, AI Chat,
> AI Screener) **without breaking current functionality**.

---

## 1. Current State (what we're building on)

| Layer | What exists today |
|-------|-------------------|
| **Auth table** | `user_id_security` (PG): `id` UUID, `email`, `username`, `password_hash`, `is_email_verified`, `status` enum(active/banned/suspended/paused), timestamps |
| **Tokens** | `email_verification_tokens`, `password_reset_tokens` (PG) |
| **Sessions** | Redis, 7-day TTL, HTTP-only cookie `session_id` → `{user_id, username, email}` |
| **Backend auth** | `auth_routes.py`, `postgres_models.py` (`UserRepository`, `TokenRepository`), `get_current_user()` dependency |
| **Monitor List** | `user_monitor_list` (PG) + 4 endpoints in `main.py`; **hardcoded `max = 5`**; localStorage for anon, PG for authed |
| **AI features** | `ai/ai_router.py`: `/api/ai/chat` (SSE), `/api/ai/screener`, `/api/ai/reports`, `/api/ai/usage`. Deepseek backend. **Token usage tracked globally in-memory** (`DeepseekClient.total_*_tokens`), not per-user. `user_id` defaults to `"anonymous"`. |
| **Frontend** | `AuthContext.js`, `UserMenu.jsx` (header), auth modals, `AI/ChatPanel.jsx`, `AI/Screener.jsx` |

**Key takeaway:** the foundation (auth, sessions, per-user monitor list) is solid.
What's missing is: tiers, a credits wallet/ledger, per-user AI metering, anonymous
gating, referrals, and a profile UI. Nothing below requires reworking auth — it's
all additive.

---

## 2. Design Decisions (with rationale)

### 2.1 Credits: per-call vs. per-token? → **Action-based credits, token-logged underneath**

You asked whether to meter by "1 credit = 1 API call" or by tokens. Recommendation: **a hybrid.**

- **User-facing unit = "Matrix Credits", priced per *action*** (chat message, screener
  query), with the cost-per-action stored in a **config table** (not hardcoded).
  Launch at the intuitive **1 credit = 1 action**, exactly as you imagined.
- **Internally, log real token usage + cost per request** in a ledger.

Why not pure per-call? A single AI Chat turn runs a multi-round tool loop (up to 5
rounds in `deepseek_client.py`) and can cost **10–20×** a simple screener query.
Flat per-call under-prices heavy chat and over-prices light screening.

Why not pure per-token? "You have 47,213 credits" is meaningless to users, creates
anxiety, and is hard to advertise.

**Industry precedent:** consumer AI products almost universally use action quotas at
the consumer tier (Perplexity "300 Pro searches/day", Cursor "500 fast requests/mo",
ChatGPT message caps) and reserve token-metering for API/enterprise. We mirror that:
simple credits for users, token telemetry for *us*.

The config table lets you later say "chat = 2 credits, screener = 1" or "charge per
tool-round" with **zero migration**.

### 2.2 Tiers & a single source of truth for entitlements

Three tiers: `anonymous` (no account), `base` (free, auto on register), `premium` (paid).

The #1 maintainability risk is scattering magic numbers (today's `>= 5` in monitor-list
is exactly this). Fix: **one central entitlements map**, read by the backend for
enforcement and exposed to the frontend so the UI never drifts from the rules.

```python
# backend/entitlements.py
ENTITLEMENTS = {
    "anonymous": {"monitor_max": 5,  "ai_monthly_credits": 0,   "anon_ip_ai_limit": 10},
    "base":      {"monitor_max": 10, "ai_monthly_credits": 100, "anon_ip_ai_limit": None},
    "premium":   {"monitor_max": 20, "ai_monthly_credits": 500, "anon_ip_ai_limit": None},
}
AI_ACTION_COST = {"chat": 1, "screener": 1}   # config-driven, see 2.1
```

New endpoint `GET /api/me/entitlements` returns the caller's effective limits +
current balances so the frontend shows correct caps and disables buttons correctly.

### 2.3 Credit wallet: spend order & monthly refresh

- **Two buckets:** `base_credits` (monthly refresh, **no rollover**) and
  `boost_credits` (**never expire**, from referrals/purchases).
- **Spend order: base first, then boost.** Preserves the non-expiring bucket for the
  user — standard and user-friendly.
- **Monthly refresh = lazy, not cron.** On every balance read/spend: if the wallet's
  stored period is older than the current month, reset `base_credits` to the tier
  default and stamp the new period. This avoids a midnight job over 10k+ users and
  naturally handles inactive accounts. Month boundary defined in **one timezone**
  (recommend US/Eastern to match the app's market-data convention) and documented.

### 2.4 Correctness: append-only ledger + atomic spend

Credits are quasi-money → must be **auditable and race-safe**.

- Every change writes a row to `credit_ledger` (append-only): action, delta,
  balance_after, token counts, cost. The wallet row is a fast cache of the balance;
  the ledger is the truth.
- Spend happens inside a PG transaction with `SELECT ... FOR UPDATE` on the wallet
  row, so two concurrent AI calls can't double-spend the last credit.
- **Charge on success.** For streaming chat: check balance at start (reject if 0),
  commit the spend + log tokens after the stream completes. If the call errors before
  output, don't charge.

### 2.5 Anonymous metering (the registration nudge)

**Decision: 10 lifetime AI actions per IP** (your original spec, locked).

Going lifetime changes *where* this is stored — a self-expiring Redis key no longer
works, because "lifetime" needs durability and an ever-growing keyspace:

- **Source of truth = Postgres** `anon_ai_usage` (§3.6), keyed by a **hashed** IP
  (`sha256(ip + server_salt)`), not the raw IP — storing IPs forever is PII; hashing
  keeps it privacy-safe while still counting uniquely.
- **Redis read-through cache** in front so we don't hit PG on every request: cache
  "blocked/count" per `ip_hash`; PG is written only for the first ~10 actions per IP,
  after which it's a cheap cached "blocked". (Keeps load off the PG pool you've already
  had to tune for connection exhaustion.)
- Keep a **localStorage** counter as a second signal so a brand-new IP+browser still
  gets its nudge (defense-in-depth; not relied upon).
- When exceeded → `402` with a structured payload → "Register free to unlock 100
  monthly credits" modal.

**Tradeoff you're accepting (informed):** a genuine returning visitor on a
previously-used IP — and everyone behind a shared IP (office/campus/mobile NAT) —
is permanently capped at 10 total. That's the strongest registration push of the three
windows, which is the intent. The cap (10) lives in `ENTITLEMENTS`, so it's a one-line
bump if it proves too stingy (10 *lifetime* is on the stingy side; easy to revisit).

> Lighter alternative if you'd rather spare PG entirely: a Redis key with a 1-year TTL
> ("effectively lifetime"), accepting that a Redis flush resets counts. Fine for a soft
> nudge, but not truly durable — I went with PG source-of-truth for real lifetime.

### 2.6 Tier switches & the credit wallet (LOCKED 2026-06-25)

`user_id_security.tier` is a **fast cache**; the source of truth for "is premium" is an
**active subscription with `current_period_end > now`**. If a subscription lapses, the
tier flag is stale → evaluated as `base` and lazily corrected (same cache/truth split
as wallet↔ledger). Every switch writes a `tier_changes` audit row (migration 002).

Because `base_credits` is use-it-or-lose-it monthly, there's no cross-month proration —
only the switch moment matters. A switch is an **explicit, ledger-logged credit
operation**, never a silent tier flip (a flip alone wouldn't change `base_credits`
until the next monthly refresh):

- **Base → Premium (upgrade):** set `base_credits = 500`, stamp current period, ledger
  `action='tier_upgrade'`. They paid → full premium quota immediately. `boost_credits`
  untouched.
- **Premium → Base (downgrade/lapse):** **keep the current month's credits** (do NOT
  claw back — clawing back what they had for the period generates support tickets); the
  next lazy monthly refresh naturally drops to 100. `boost_credits` untouched (never
  expire, tier-independent).

Implementation lands in **Phase 5** (premium activation); the schema (migration 002:
`subscriptions` period/lifecycle dates + `tier_changes`) is already applied.

---

## 3. Database Schema Changes

Rationale for new tables vs. cramming into `user_id_security`: keep the auth table
small and fast (it's read on every authenticated request); isolate high-churn credit
writes; keep append-heavy audit logs separate. This matches the existing pattern
(tokens already live in their own tables).

### 3.1 Extend `user_id_security`

```sql
DO $$ BEGIN
    CREATE TYPE user_tier AS ENUM ('base', 'premium');
EXCEPTION WHEN duplicate_object THEN null; END $$;

ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS tier user_tier DEFAULT 'base';
ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS referral_code VARCHAR(12) UNIQUE;
ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS referred_by UUID REFERENCES user_id_security(id);
```

### 3.2 `user_credits` (1:1 wallet — fast balance cache)

```sql
CREATE TABLE IF NOT EXISTS user_credits (
    user_id UUID PRIMARY KEY REFERENCES user_id_security(id) ON DELETE CASCADE,
    base_credits INT NOT NULL DEFAULT 100,
    base_period DATE NOT NULL DEFAULT date_trunc('month', NOW())::date,  -- month these belong to
    boost_credits INT NOT NULL DEFAULT 0,                                -- never expires
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 `credit_ledger` (append-only audit + token analytics)

```sql
CREATE TABLE IF NOT EXISTS credit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    action VARCHAR(32) NOT NULL,        -- chat | screener | monthly_refresh | referral_bonus | purchase | admin_adjust
    credits_delta INT NOT NULL,         -- negative = spend, positive = grant
    bucket VARCHAR(8) NOT NULL,         -- base | boost
    balance_after INT NOT NULL,
    ref_type VARCHAR(32), ref_id VARCHAR(64),   -- e.g. conversation_id / screener query hash
    input_tokens INT, output_tokens INT, cost_usd NUMERIC(10,6),  -- analytics
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ledger_user_time ON credit_ledger(user_id, created_at DESC);
```

### 3.4 `referrals` (growth loop + fraud audit)

```sql
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referred_user_id UUID UNIQUE NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referral_code VARCHAR(12) NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending',  -- pending | approved | rewarded | rejected
    referrer_reward INT NOT NULL DEFAULT 100,
    referee_reward INT NOT NULL DEFAULT 50,         -- double-sided: new user welcome boost (LOCKED §8)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
```

### 3.5 `subscriptions` (PLACEHOLDER — no payment integration yet)

```sql
-- STUB: shape only, so flipping to paid later is just wiring a provider (Stripe/etc.)
-- Lifecycle date columns + tier_changes added in migration 002 (see §2.6).
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    plan VARCHAR(16) NOT NULL DEFAULT 'premium',
    status VARCHAR(16) NOT NULL DEFAULT 'inactive',  -- inactive | active | past_due | canceled
    provider VARCHAR(16), provider_ref VARCHAR(128),  -- filled in when payment is added
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    started_at TIMESTAMPTZ,                            -- first time ever became premium
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tier-change audit trail (tier on user_id_security is a fast cache; this is history)
CREATE TABLE IF NOT EXISTS tier_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    from_tier user_tier, to_tier user_tier NOT NULL,
    reason VARCHAR(32),          -- initial | upgrade | downgrade | lapse | admin
    effective_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.6 `anon_ai_usage` (durable lifetime anon counter — see §2.5)

```sql
-- Lifetime per-IP cap for anonymous AI usage. Raw IP is NEVER stored.
CREATE TABLE IF NOT EXISTS anon_ai_usage (
    ip_hash CHAR(64) PRIMARY KEY,      -- sha256(ip + server_salt)
    count INT NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);
```

> ⚠️ `docker/postgres-init.sql` only runs on first container creation. These must be
> applied to the live DB as `ALTER`/`CREATE IF NOT EXISTS` migrations (same approach
> used for the live_quotes prev-indicator columns).

---

## 4. Backend Implementation

### 4.1 New modules

- **`entitlements.py`** — the `ENTITLEMENTS` / `AI_ACTION_COST` maps + helpers.
- **`credits_service.py`** — `CreditsService`:
  - `get_wallet(user_id)` → lazy monthly refresh, returns `{base, boost, period, resets_on}`
  - `spend(user_id, action, tokens=None)` → atomic (txn + `FOR UPDATE`), base-then-boost, writes ledger; raises `InsufficientCredits`
  - `grant(user_id, amount, reason, bucket="boost")` → referrals/purchases/admin
  - `history(user_id, limit)` → ledger rows for the profile usage page
- **`anon_usage.py`** — `AnonUsageService` over Redis: `check(ip)`, `increment(ip)`.
- **`referral_service.py`** — code generation, capture on register, auto-approval rule, reward grant.

### 4.2 Wire AI endpoints to credits

A FastAPI dependency gates `/api/ai/chat` and `/api/ai/screener`:

```python
async def require_ai_quota(action: str, request, session_id):
    user = await get_current_user(session_id)
    if user:
        wallet = await credits.get_wallet(user["user_id"])
        if wallet.total < AI_ACTION_COST[action]:
            raise HTTPException(402, detail={"reason": "insufficient_credits", "tier": user["tier"]})
        return {"user_id": user["user_id"], "charge": True}   # commit after success
    # anonymous
    ip = client_ip(request)
    if not await anon_usage.check(ip):
        raise HTTPException(402, detail={"reason": "anon_limit", "limit": 10})
    await anon_usage.increment(ip)
    return {"user_id": "anonymous", "charge": False}
```

- Chat: check at start → stream → on success `credits.spend(user_id, "chat", tokens)`.
- Also pass the real `user_id` into the chat agent so conversations are stored
  per-user (today everything is `"anonymous"`).
- Add a lightweight **per-user rate limit** (e.g. 20 req/min via Redis) so credits
  aren't the only abuse defense.

### 4.3 Refactor existing hardcoded limits

Replace monitor-list `if count >= 5` with `entitlements[tier]["monitor_max"]`, and
apply the same cap in the `add` and `sync` endpoints. Anonymous stays at 5 via
localStorage (already built). This is the moment the existing feature becomes
tier-aware.

### 4.4 Register flow additions

On register: generate a unique `referral_code`; if a `ref` code was supplied, create a
`referrals` row (`pending`) and stamp `referred_by`. On email-verify (the existing
auto-login step): create the `user_credits` row (100 base) and run referral
auto-approval (§6 anti-fraud rules) → grant referrer 100 boost via ledger.

---

## 5. Frontend Implementation

- **`AuthContext.js`** — extend `user` with `tier`; add `credits` (`{base, boost,
  resetsOn}`), `entitlements`, `referralCode`; add `refreshCredits()`. Fetch from
  `/api/me/entitlements` after login and after each AI action.
- **New `ProfilePage.jsx`** (`/profile`):
  - Account: username, email + verified badge, member-since, tier badge
  - **Credits dashboard:** base `X/100 — resets <date>`, boost `Y — never expires`,
    and a usage history list (from `credit_ledger`)
  - **Referral card:** your link `https://app/?ref=CODE`, copy button, # successful
    referrals, credits earned
  - **Upgrade card:** Base vs Premium comparison table + "Upgrade" CTA →
    **placeholder** modal ("Premium coming soon")
- **`UserMenu.jsx`** — add "Profile" entry + a header credits chip (e.g. `⚡ 87`).
- **Gating UX (the funnel):**
  - Show "you've used 8/10" *before* the wall (soft paywall) so the nudge lands.
  - Blocked anon → "Register free to unlock 100 monthly credits" modal.
  - Base at 0 credits → "Invite friends for boost credits / Upgrade to Premium."
  - Monitor "+" at tier cap → tooltip "Upgrade to add more."
- **Referral capture:** read `?ref=CODE` on app load → localStorage → send with
  registration payload.

---

## 6. Critique of Your Plan — Gaps, Risks & Refinements

**What's strong:** freemium with a registration wall on a cheap-but-valuable action
(AI) is a proven funnel; non-expiring boost credits are a great viral lever;
use-it-or-lose-it monthly credits give a predictable cost ceiling *and* drive habit.

**Gaps / risks to fix:**

1. **Per-IP anon limit is weak by nature** (shared IPs pool, mobile IPs rotate) — so
   treat it as a *nudge*, not security, and pair it with a localStorage counter.
   **Decision (§8): lifetime cap**, accepted with eyes open; the durability + privacy
   consequences are handled in §2.5 (PG source-of-truth, hashed IP, Redis cache).
2. **"1 credit = 1 call" mis-prices.** Tool-using chat ≫ screener. Keep 1:1 at launch
   but make cost-per-action config-driven + log tokens underneath (§2.1).
3. **Referral fraud** (self-referral, disposable emails, account farming for 100
   credits each). Mitigations baked in: reward only **after** the referee verifies
   email; reject self/duplicate; block disposable-email domains; one reward per
   referee; cap rewarded referrals per period; velocity flags; full `referrals` audit.
4. **Financial correctness.** Credits ≈ money → append-only ledger + atomic
   `FOR UPDATE` spend (never mutate a bare balance). Already in the design (§2.4).
5. **Monthly refresh at scale.** Lazy refresh on access, not a midnight cron; pin the
   month boundary to one timezone (§2.3).
6. **Premium downgrade.** When premium lapses, a user may have 11–20 monitor stocks.
   **Don't delete their data** — grandfather existing entries as read-only and block
   *adding* until under the base cap. Define this explicitly.
7. **AI budget abuse by registered users.** Credits cap cost, but add a per-user
   rate limit too (§4.2).
8. **Admin/testing.** Add an admin-only "set tier"/"grant credits" path so you can
   test premium before payments exist.

**Refinements borrowed from successful products:**

- **Double-sided referral** (Dropbox/PayPal/Wise): reward *both* sides. Giving the new
  user a small welcome boost (e.g. +50) typically lifts referral conversion far more
  than a one-sided reward. Schema already supports `referee_reward`.
- **Onboarding quests / streaks** (Duolingo/Perplexity): tiny boost grants for first
  chat, completing profile, daily visit — engagement at near-zero cost.
- **Transparent usage meter** (OpenAI/Anthropic/Cursor consoles): the ledger-backed
  history page builds trust and cuts "where did my credits go?" support load.
- **Tier comparison at the upgrade moment** (every SaaS): show Base vs Premium side by
  side exactly when the user hits a wall.

---

## 7. Phased Rollout (each phase ships independently, no big-bang)

| Phase | Scope | User-visible? |
|-------|-------|---------------|
| **0** ✅ | Schema migrations + `entitlements.py` config. No behavior change. | No |
| **1** ✅ | `CreditsService` + ledger + wire AI endpoints to spend (base tier) + monitor-list tier cap + `/api/me/entitlements`. | Credits start counting |
| **2** ✅ | Anonymous per-IP gating (`anon_ai_usage` + Redis cache, hashed IP) wired into AI endpoints + register-to-unlock gate/modal in Chat & Screener. | Yes (funnel) |
| **3** ✅ | Referral system: code generation (**Gap A FIXED** in `create_user`), `?ref` capture → `referred_by` + pending `referrals` row, email-verify auto-approval, double-sided +100/+50 boost grants, `/api/referral`. Migration 003 (`referred_by` ON DELETE SET NULL). Also fixed a latent module-level `postgres_db` NameError that broke the authed monitor-list endpoints. | Yes |
| **4** ✅ | Profile page (`/profile`): account header (tier badge, verified, member-since/last-login), credits dashboard, referral card w/ copy-link, usage history, header `⚡` credits chip. `last_login_at` added + stamped on login (Gap B sliver). Deferred (Gap B): display/full name, avatar image, bio, preferences. | Yes |
| **5** ✅ | Tier-switch logic (§2.6) in `TierService`: upgrade → 500 + ledger + `tier_changes` + active subscription; downgrade → credits kept + subscription canceled; lazy refresh drops to 100 next month. `is_admin` (migration 005) + admin tier-toggle/grant endpoints + profile admin control. Payment = **placeholder**. | Soft |
| **6** ✅ | Polish: double-sided referral (P3), downgrade credit handling (P5), **monitor-list grandfathering** — tier-aware cap (anon 5 / base 10 / premium 20) via `entitlements.monitor_max`; over-cap stocks preserved (downgrade never deletes) + adds blocked w/ message until under cap. Optional onboarding quests deferred. | Yes |
| **7** ✅ v1 | `activity_events` (MongoDB) + `ActivityService` (indexed, fire-and-forget). Backend-derived events: **screener_query (text, per user — verified live)**, chat_message, login, signup; `GET /api/me/activity`. Deferred: frontend tracker for client-only signals (page/ticker_view), profile "recent activity" UI. See §9. | Mostly internal |

**Backward-compat guarantees:** auth, sessions, and the existing monitor-list/AI
endpoints keep working throughout; Phase 0–1 are additive; the only refactor is
replacing the hardcoded `5` with the entitlements lookup.

---

## 8. Locked Decisions (2026-06-25)

1. **Reset window:** calendar month, **US/Eastern** — one timezone convention,
   consistent with the app's market-date / scheduler boundaries. Lazy-refresh period =
   `date_trunc('month', NOW() AT TIME ZONE 'US/Eastern')`.
2. **Double-sided referral:** referrer **+100 boost** *and* the new user gets a welcome
   **+50 boost** (`referrals.referee_reward = 50`). Both non-expiring.
3. **Referral approval:** **email-verified only** — auto-approve the moment the referred
   user verifies their email; one reward per referee; reject self-referral.
4. **Anon limit:** **10 lifetime per IP**, stored durably in Postgres (`anon_ai_usage`,
   hashed IP) + Redis read-through cache (§2.5). Accepted tradeoff: shared/returning IPs
   are permanently capped.
5. **Action costs at launch:** chat = screener = **1 credit**. Cost stays config-driven
   (`AI_ACTION_COST`) so chat can be re-priced later with no migration.

---

## 9. Phase 7 — Analytics & Activity Tracking (design)

Goal: understand what users do (for product analytics, engagement metrics, and later
personalization) without bloating the operational DB or building a premature
clickstream. **Orthogonal and non-blocking** — nothing in Phases 0–6 depends on it.

### 9.1 What already exists (do NOT rebuild)

| Activity | Already captured | Where |
|----------|------------------|-------|
| AI **chat** conversations (full Q&A, per user) | ✅ | MongoDB `ai_conversations` (`user_id` + `conversation_id`, system/user/assistant turns) |
| AI **usage events** (chat/screener + timestamp) | ✅ | `credit_ledger` (action, created_at) |
| Anonymous AI usage counts | ✅ | `anon_ai_usage` (hashed IP) |
| Login events / `last_login_at` | ❌ | — (first sliver pulled into Phase 4) |
| Page / ticker / feature views | ❌ | — (new; the core of this phase) |

Notes on the existing chat data: single messages > 10k chars are truncated; tool
steps are not stored (only final assistant text); anonymous chats are all lumped under
`user_id = "anonymous"`. A dedicated `user_ai_conversation` table would be **redundant**
— content is in Mongo, events are in the ledger.

### 9.2 Design decisions

1. **Track semantic events, not raw clicks/keystrokes.** Named events with properties
   (`ticker_view {symbol}`, `screener_query {text}`, `login`) — not DOM noise. ~95% of
   the value at ~5% of the volume.
2. **Store the event stream in MongoDB, not Postgres.** High-volume append-only writes
   would worsen the PG connection-pool pressure we already had to tune (credits/auth
   depend on that pool). Mongo is already in the stack and write-friendly. Keep Postgres
   for transactional state. (A tool like PostHog is the *later* step if dashboards are
   wanted — don't start there.)
3. **Derive events server-side first; instrument the frontend only where required.**
   `login`, `ticker_view` (chart-data endpoint), `screener_query`, `chat_message` are all
   visible at the API layer with near-zero frontend work. Add a `POST /api/activity/batch`
   endpoint + lightweight tracker only for client-only signals (tab switch, time-on-page,
   scroll depth).
4. **Privacy.** Behavioral data is PII: privacy-policy line, retention limit (purge raw
   events after N months), hash anonymous IPs (as `anon_ai_usage` already does), never log
   secrets/credentials.

### 9.3 Schema

**`activity_events`** (MongoDB):
```
{ user_id | anon_session, event_type, properties: {}, ts, session_id, ip_hash? }
```
Indexes: `(user_id, ts)`, `(event_type, ts)`.

**Event taxonomy (~10 to start):** `login`, `logout`, `signup`, `page_view`,
`ticker_view`, `screener_query`, `chat_message`, `monitor_add` / `monitor_remove`,
`report_view`, `referral_click`.

### 9.4 Service + wiring

- **`ActivityService.log(event_type, user_id, props)`** — fire-and-forget insert into
  `activity_events`; called inline from existing endpoints (a couple of lines each).
- **`POST /api/activity/batch`** — accepts client-only events from the frontend tracker.

### 9.5 Screener query logging (EXPLICIT REQUIREMENT — locked 2026-06-25)

The AI Screener currently does **not** persist its query text anywhere (only the fact
that a screener action happened is in `credit_ledger`, without the text). Requirement:
**log every screener query text per user.** Implementation in this phase: in the
screener endpoint, after a successful (or attempted) screen, emit a `screener_query`
activity event `{ user_id, text, result_count, ts }` into `activity_events`. For
logged-in users this is attributed to `user_id`; for anonymous, to the hashed IP /
anon session. (Small, self-contained — can be pulled forward as a quick win if desired,
but the event-stream infra lives here.)

### 9.6 Fit & sequencing

Build **after** the core user system (you want registered users and a profile to make
tracking worthwhile). First sliver — `last_login_at` + a couple of backend-derived
events — is pulled into **Phase 4** since the profile page is the natural place to
surface "your recent activity."
