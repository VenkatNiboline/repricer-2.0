# QA Tester Brief: Amazon Repricer (Pricing Tool)

This document describes the internal **Amazon FBA/FBM pricing management tool** for experienced QA testers. It covers product purpose, architecture, critical workflows, and test priorities.

---

## 1. Product Overview

### What is the app?

An internal web tool for **Amazon FBA/FBM price management**. Sellers set FBA prices; the app automatically syncs linked SKUs (pack-size variations, FBM counterpart listings), logs all changes, and verifies whether Amazon actually applied the prices.

### Core problems solved

- Consistent pricing across **pack sizes** (e.g. single vs. double pack → proportional pricing)
- Automatic **FBM synchronization** (default: 10% below FBA)
- **Min/max bounds** per SKU and marketplace
- **Audit trail** and **verification** against Amazon
- **Sales analytics** and **QC checks** for data quality and pricing signals

### Target users

Internal pricing team / admin users with Amazon SP-API access.

---

## 2. New Features in This Release

The following capabilities were added on top of the core repricing tool. **Prioritize these in regression testing.**

| Feature | Route / API | What it does |
|---------|-------------|--------------|
| **Overview dashboard (batched KPIs)** | `/` · `GET /api/overview` | Single call loads catalog total, 7-day sales revenue/units, and open QC alert counts (critical + warning) |
| **Sales performance** | `/sales` · `GET /api/sales/summary` | 7-day revenue, units, and row count from `sales_daily` |
| **Sales detail (per SKU)** | `/sales/:sku` · `GET /api/sales?sku=` | 30-day daily breakdown: revenue, units, sessions, buy box % |
| **Sales ETL from Amazon** | `POST /api/sales/sync` | Fetches Sales & Traffic report, upserts `sales_daily`, runs features engine + QC |
| **Pricing features engine** | `lib/features_engine.py` | Computes `units_7d`, `revenue_7d`, `buy_box_avg_7d`, `signal_underpriced_high_demand` per SKU |
| **QC dashboard** | `/qc` · `POST /api/qc/run` | Three agents: repricing, data, pricing — findings list with resolve |
| **Price reflection** | History + `lib/price_reflection.py` | Tracks whether Amazon adopted pushed prices (`pending` → `reflected` / `mismatch` / `timeout`) |
| **Multi-marketplace (9 EU)** | Header `MarketplaceSelector` | Per-country catalog tables, currency, region; switches context app-wide |
| **Supabase auth & roles** | Login page · `/api/auth/*` | Cookie-based login; first user = admin; BFF pattern (no keys in browser) |
| **Per-marketplace catalog DB** | `sku_catalog_{country}` | Separate tables + unified view; cron sync for DE only |
| **Vercel deployment** | `vercel.json` | SPA + serverless FastAPI in one deployment |

### Post-repricing automation

After every **live** repricer push, the backend automatically:

1. Runs `verify_pending_reflections()` on open history rows
2. Runs `repricing_qc` agent

### Post-sales-sync automation

After **sales sync** (admin), the backend automatically:

1. Upserts rows into `sales_daily`
2. Runs `run_features_engine(country)` (up to 100 catalog SKUs)
3. Runs `data_qc` + `pricing_qc` agents

---

## 3. Architecture (High-Level)

```
┌─────────────┐     /api/*      ┌──────────────┐     SP-API      ┌─────────┐
│  React UI   │ ──────────────► │  FastAPI BFF │ ──────────────► │ Amazon  │
│  (Vite)     │                 │  (Python)    │                 └─────────┘
└─────────────┘                 └──────┬───────┘
                                       │
                                       ▼
                               ┌──────────────┐
                               │   Supabase   │
                               │ (Postgres +  │
                               │  Auth + RLS) │
                               └──────────────┘
```

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL, Auth, RLS, Edge Functions, pg_cron) |
| Deployment | Vercel (SPA + serverless API) |
| Amazon | SP-API: Listings Items API, Reports API (Sales & Traffic) |

**Important for QA:** The frontend talks **only** to `/api` (BFF pattern). No Supabase keys in the browser. Amazon credentials are server-side only.

**Local development:** API on `:8000`, UI on `:5173` with Vite proxy `/api` → `127.0.0.1:8000`.

---

## 4. User Roles and Authentication

| Role | Permissions |
|------|-------------|
| **admin** | Rules CRUD, write app settings, sales sync, full read access |
| **user** | Read (history, rules, catalog, QC), repricing, resolve QC findings |
| **local-dev** | When auth is **not** configured — full API access without login |

### Auth mechanism

- Supabase Auth with httpOnly cookies (`repricer_at` 1h, `repricer_rt` 7d)
- Cookies: `httponly`, `samesite=strict`, `secure` on Vercel
- Alternative: `Authorization: Bearer <token>`
- **First registered user** is automatically assigned `admin` (DB trigger)

### Auth modes

| Mode | Behavior |
|------|----------|
| Auth disabled | No login, `user_id="local-dev"`, history still needs service role key |
| Auth on, not logged in | UI shows login page |
| Auth on, user | Cookie session |
| Auth on, admin | Rules, settings, sales sync |

### QA note

The **UI does not hide admin actions**. Non-admins can see buttons like "Save rules" or "Sales sync" — the API returns **403**. Test UI vs. API permission behavior explicitly.

---

## 5. Pages and Features

| Route | Page | Function |
|-------|------|----------|
| `/` | Overview | Batched KPIs (catalog, sales 7d, QC alerts), API health indicator, sync catalog, quick links |
| `/catalog` | SKU Catalog | Full catalog with search, FBA/FBM filter, sync, CSV export |
| `/reprice` | Reprice | **Core workflow:** SKU + price → preview → dry-run or live push to Amazon |
| `/sales` | Sales Performance | 7-day revenue/units summary, refresh, admin sales sync |
| `/sales/:sku` | Sales Detail | Per-SKU 30-day table: date, revenue, units, sessions, buy box % |
| `/rules` | SKU Rules | Min/max, FBM discount, sync flags per SKU (admin writes) |
| `/history` | History | Price history with reflection status, manual re-verify |
| `/qc` | QC Dashboard | Open findings, run QC, resolve findings |
| `/fbm` | FBM Catalog | FBM SKUs only, CSV export |
| `/settings` | Settings | Marketplace, region, sync flags, FBM discount, dry-run default |
| (login) | Login | Sign-in / sign-up when auth is configured |

### Marketplace selector (header)

The **MarketplaceSelector** dropdown in the header sets `settings.country` and `settings.region` for the entire app. Changing marketplace reloads data on Overview, Sales, Catalog, History, Reprice, etc.

**9 options:** DE, FR, IT, ES, NL, BE, PL, SE, UK — each with label and currency shown in the dropdown.

**Auth gate:** When `SUPABASE_URL` + `SUPABASE_ANON_KEY` are set → login required. Without auth → app runs in open local-dev mode.

---

## 6. Critical Business Rules

These rules are **central** to functional testing.

### FBM synchronization

- **FBM price** = `FBA × (1 − discount)` — default discount: **10%**
- **FBM SKU** = FBA SKU + suffix `FBM` (e.g. `7770531` → `7770531FBM`)
- FBM update only happens if the FBM SKU exists on Amazon

### Variation sync (pack sizes)

- Only **larger** pack sizes with an **integer unit ratio** (2×, 3×, …)
- Optional: **double packs only** (`double_only`)
- `same_product_line`: ml volume must match; piece count from `size_label` vs. `units` must be consistent
- `exclude_skus`: exclude specific SKUs from variation sync

### SKU rules

- Override request defaults for min/max, FBM discount, `sync_siblings`, `sync_fbm` — **only when field is set** (not `null`)
- Price below `min` → clamped to `min`; above `max` → clamped to `max`

### FBM SKU as input

- Entering an FBM SKU → `normalize_fba_anchor` converts back to the FBA anchor price

### Reflection (price adoption on Amazon)

- After live push: immediate verification (`verify=true`) with tolerance **0.01**
- Async: up to 30 attempts / 30 minutes → then `timeout` or `mismatch`
- Dry-run and failed push → `reflection_status = not_applicable`

---

## 7. Core Workflows (Test Priority)

### A. Repricing (highest priority)

```
1. Select marketplace (e.g. DE)
2. Go to /reprice → enter FBA SKU + target price
3. Preview → table shows: primary | variation (pack ×N) | fbm (×0.90)
4. Dry-run → Amazon VALIDATION_PREVIEW, no push, history with dry_run=true
5. Live push → real PATCH, verify, history with reflection_status
6. After live push: automatic reflection check + repricing_qc
```

**Test cases:**

- SKU with variations and FBM pair
- SKU rule with min/max (clamping)
- `double_only`, `exclude_skus`
- FBM SKU as input
- Dry-run vs. live
- `history_saved=false` when `SUPABASE_SERVICE_ROLE_KEY` is missing

**Repricer request body (important):**

`sku`, `price`, `country`, `region`, `dry_run` (default `true`), `verify`, `sync_siblings`, `sync_fbm`, `double_only`, `fbm_discount`, `exclude_skus`

### B. Rules (admin)

- Create/update/delete rules
- Reprice with price below min → clamped to min
- Non-admin: PUT/DELETE → **403**

### C. Catalog

- Sync triggers live Amazon scan (~889 SKUs per cron comment)
- **Sync all 9** runs sequentially across EU marketplaces
- Data source fallback: `supabase` → `cache` (JSON in `data/cache/`) → `empty`
- FBM filter, search by SKU/ASIN/product name

### D. History

- Filtered by `settings.country`
- Badges: Dry run, Failed, Pending, Reflected, Mismatch, Timeout
- **Recheck** calls `/api/history/{id}/verify`
- Auto-refresh on tab focus (`visibilitychange`)

### E. Overview dashboard

```
1. Select marketplace in header (e.g. DE)
2. Go to / → Overview loads GET /api/overview in one request
3. Verify KPI cards: Total SKUs, Revenue (7d), Units (7d), QC alerts
4. QC alerts hint shows "N critical · M warning"
5. API health dot: green = /api/health OK, red = unreachable
6. "Sync {country}" triggers catalog sync for current marketplace only
7. Quick links navigate to /sales, /qc, /history
```

**Test cases:**

- Switch marketplace → all KPIs reload for new country
- No Supabase configured → overview returns zeros (no crash)
- Catalog synced recently → "Total SKUs" hint shows last sync timestamp
- Open QC findings exist → QC alerts card reflects `open_qc_total`
- API down → red health indicator, error on failed overview load

### F. Sales performance & detail

**Sales Performance (`/sales`):**

```
1. Select marketplace
2. Page loads GET /api/sales/summary?country=XX
3. Shows Revenue (7d), Units (7d), Data rows
4. Admin: "Sync sales (7d)" → POST /api/sales/sync (can take up to ~10 min)
5. After sync: features engine + data_qc + pricing_qc run automatically
```

**Sales Detail (`/sales/:sku`):**

```
1. Navigate directly to /sales/{SKU} (no link from Sales Performance page yet)
2. Loads GET /api/sales?country=XX&sku={SKU}&days=30
3. Summary cards: Revenue (30d), Units (30d), Data points (row count)
4. Table columns: Date, Revenue, Units, Sessions, Buy box %
5. Empty state: "No sales data for this SKU. Run a sales sync first."
6. "Back" returns to /sales
```

**Test cases:**

- Sales sync as admin → rows appear in summary and detail
- Sales sync as non-admin → **403**
- SKU with no sales data → empty table + message on detail page
- Change marketplace on detail page → data reloads for new country
- Revenue display uses hardcoded `EUR` on detail page — verify for UK (GBP), PL (PLN), SE (SEK)
- Sessions and buy box % show "—" when null in source data

### G. QC

Three QC agents run via `POST /api/qc/run` (all agents) or automatically after sales sync / live repricing:

**repricing_qc** (`lib/qc/repricing_qc_agent.py`):

| check_id | Severity | Trigger |
|----------|----------|---------|
| `reflection_pending_stale` | warning | `reflection_status=pending` and pushed > 30 min ago |
| `reflection_mismatch` | critical | `reflection_status=mismatch` |
| `reflection_timeout` | warning | `reflection_status=timeout` |
| `push_failed` | critical | `pushed=false`, `dry_run=false` |

**data_qc** (`lib/qc/data_qc_agent.py`):

| check_id | Severity | Trigger |
|----------|----------|---------|
| `no_sales_data` | info | No rows in `sales_daily` |
| `stale_data` | warning | Latest sales date older than 2 days |
| `duplicate_rows` | critical | Duplicate (marketplace, ASIN, date) keys |
| `missing_sku_mapping` | warning | Sales ASIN not found in catalog |
| `currency_mismatch` | warning | Sales currency ≠ catalog currency |
| `negative_metrics` | critical | Negative revenue or units |
| `null_sales_with_traffic` | warning | Sessions > 0 but no sales/units |

**pricing_qc** (`lib/qc/pricing_qc_agent.py`):

| check_id | Severity | Trigger |
|----------|----------|---------|
| `signal_underpriced` | info | `signal_underpriced_high_demand` feature = 1 (units ≥ 10, buy_box_avg ≥ 90%, sessions > 0) |

**QC dashboard UI:**

- Lists unresolved findings (`GET /api/qc/findings?resolved=false`)
- "Run QC" triggers all three agents
- "Resolve" per finding → `PATCH /api/qc/findings/{id}`
- Severity badges: critical, warning, info

**Note:** `config/pricing_features.yaml` defines `signal_overpriced_low_traffic`, but it is **not yet implemented** in the features engine — only `signal_underpriced_high_demand` is computed today.

---

## 8. Multi-Marketplace Support

**9 EU marketplaces:** `DE`, `FR`, `IT`, `ES`, `NL`, `BE`, `PL` (PLN), `SE` (SEK), `UK` (GBP)

- Separate DB table per country: `sku_catalog_de`, `sku_catalog_fr`, …
- **Cron sync is DE only** (every 6 hours) — other countries require manual sync (UI "Sync all 9" or API)
- Currency per country in API; sales page may show revenue hardcoded as `€` — possible display bug for UK/PL/SE

---

## 9. API Overview

### Health

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/health` | Status, `auth_configured`, `db_configured` | No |

### Auth

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/auth/status` | Whether auth is configured | No |
| GET | `/api/auth/me` | Current user + role | Cookie/Bearer |
| POST | `/api/auth/login` | Login, sets httpOnly cookies | No |
| POST | `/api/auth/signup` | Registration | No |
| POST | `/api/auth/logout` | Clear cookies | No |

### Overview

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/overview` | Batched KPIs for dashboard (`country` query param) | Optional |

**Response fields:** `country`, `catalog_total`, `catalog_fba`, `catalog_fbm`, `catalog_synced_at`, `sales_revenue_7d`, `sales_units_7d`, `open_qc_critical`, `open_qc_warning`, `open_qc_total`

Returns zeros when Supabase is not configured.

### SKUs & Catalog

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/marketplaces` | Supported marketplaces + currency | No |
| GET | `/api/skus/{sku}` | Live SKU details from Amazon | No |
| GET | `/api/skus/{sku}/preview` | Preview linked price changes | No |
| GET | `/api/catalog` | Catalog from Supabase/cache | Optional |
| GET | `/api/catalog/stats` | Stats only | No |
| POST | `/api/catalog/sync` | Live Amazon scan → Supabase | Optional |
| GET | `/api/fbm-skus` | FBM SKU list | No |

### Repricer

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/api/repricer/update` | Set price (dry_run/live), variation + FBM sync | Optional |

### Rules

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/rules` | List rules | Auth if configured |
| PUT | `/api/rules` | Save rule | **Admin** |
| DELETE | `/api/rules/{sku}` | Delete rule | **Admin** |

### History

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/history` | Price history (`country`, `sku`, `limit`) | Auth if configured |
| POST | `/api/history/verify-pending` | Verify all pending reflections | Auth if configured |
| POST | `/api/history/{id}/verify` | Verify single row | Auth if configured |

### Settings

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/app-settings` | Global app settings | Auth if configured |
| PUT | `/api/app-settings` | Save settings | **Admin** |

### Sales

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/sales/summary` | 7-day aggregate | Auth if configured |
| GET | `/api/sales` | Raw data (`days`, `sku`) | Auth if configured |
| POST | `/api/sales/sync` | Amazon report → DB + features + QC | **Admin** |

### QC

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/api/qc/run` | Run QC agents | Auth if configured |
| GET | `/api/qc/findings` | Findings (`resolved`, `severity`) | Auth if configured |
| PATCH | `/api/qc/findings/{id}` | Mark finding resolved | Auth if configured |

---

## 10. Data Model (Key Entities)

| Entity | Table | Key fields |
|--------|-------|------------|
| User profile | `profiles` | `id` (UUID), `role` (admin/user) |
| App settings | `app_settings` | Singleton `id=1` |
| SKU catalog | `sku_catalog_{country}` | `sku`, `fulfillment`, `fba_pair`, `is_fbm`, `parent_sku`, `units` |
| SKU rules | `sku_rules` | `(sku, country)` unique |
| Price history | `price_history` | `reflection_status`, `link_kind`, `dry_run`, `pushed`, `verified_price` |
| Catalog sync runs | `catalog_sync_runs` | Audit |
| Sales daily | `sales_daily` | `(ob_marketplace_id, child_asin, ob_date)` unique |
| Sales sync runs | `sales_sync_runs` | Status running/completed/failed |
| Pricing features | `pricing_features_daily` | `(sku, country, feature_date, feature_id)` |
| QC runs/findings | `qc_runs`, `qc_findings` | `severity`, `resolved`, `check_id` |

**`link_kind` in history:** `primary`, `variation`, `fbm`

**`reflection_status`:** `pending` → `reflected` | `mismatch` | `timeout` | `not_applicable`

---

## 11. External Integrations

### Amazon SP-API

- **Listings Items API:** GET/PATCH listings, `searchListingsItems` for catalog
- **Reports API:** `GET_SALES_AND_TRAFFIC_REPORT` (daily, child ASIN)
- **LWA OAuth:** refresh token → access token
- **Regions:** EU (default), US, FE — endpoint `sellingpartnerapi-{region}.amazon.com`

### Supabase

- **PostgreSQL:** persistence (catalog, history, rules, sales, QC, features)
- **Auth:** users/profiles with roles
- **Edge Function `sync-catalog`:** catalog sync with cron secret or bearer token
- **pg_cron:** every 6 hours DE catalog sync (migration)

### Vercel

- Build: `python scripts/vercel_build.py` → npm build + copy to `public/`
- Rewrites: `/api/*` → FastAPI, rest → SPA

---

## 12. Background Jobs and Scripts

| Job / Script | Path | Purpose |
|--------------|------|---------|
| **pg_cron** | Migration | Every 6h DE catalog via edge function |
| **Edge function** | `supabase/functions/sync-catalog/` | Amazon → Supabase |
| `scripts/sync_catalog.py` | CLI | `--country`, `--region`, `--refresh` |
| `scripts/sync_sales.py` | CLI | `--days`, `--country` |
| `scripts/set_price.py` | CLI | Full repricer without UI |
| `scripts/vercel_build.py` | Vercel build | React → `public/` |
| `scripts/start_api.sh` / `start_ui.sh` | Local start | Dev servers |
| `scripts/sync_vercel_env.sh` | Env sync | Push env vars to Vercel |

**Post-repricing (inline, no queue):** `verify_pending_reflections()` + `repricing_qc`

---

## 13. Test Environment Setup

### Local setup

```bash
# Terminal 1
./scripts/start_api.sh    # :8000

# Terminal 2
./scripts/start_ui.sh     # :5173, /api proxied to :8000

# Health check
curl http://127.0.0.1:8000/api/health
```

### Required environment variables

**Server** (`ENV/AmazonCredentials.env` or Vercel):

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `LWA_REFRESH_TOKEN` | Amazon OAuth | SP-API |
| `LWA_CLIENT_ID` | Amazon OAuth | SP-API |
| `LWA_CLIENT_SECRET` | Amazon OAuth | SP-API |
| `SELLER_ID` | Amazon seller ID | SP-API |
| `SUPABASE_URL` | Supabase project | DB + auth |
| `SUPABASE_ANON_KEY` | Auth (server-side) | Login |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend DB write access | History, catalog, QC, sales |
| `VERCEL` / `VERCEL_URL` | Deployment | CORS, HSTS, secure cookies |
| `COOKIE_SECURE` | Cookie flag locally | Optional |
| `CRON_SECRET` | Edge function + pg_cron | Automated catalog sync |

**Frontend:** No secrets (`web/.env.example` confirms BFF-only). Local settings in `localStorage` (`repricer-settings`).

**Config files:** `config/pricing_features.yaml` — feature definitions for the features engine.

### Minimum requirements

| Scenario | Required |
|----------|----------|
| Live repricing | Amazon credentials + `SELLER_ID` |
| History, rules, QC, sales | + `SUPABASE_*` |
| Login | `SUPABASE_URL` + `SUPABASE_ANON_KEY` |

---

## 14. Edge Cases and Complex Logic

### Repricing / variations (`lib/variations.py`)

- Only siblings with **more units** than source and **integer ratio**
- `double_only`: only 2× packs
- `exclude_skus`: exclude specific SKUs from variation sync
- FBM SKU only updated if `get_listing(fbm_sku)` succeeds
- FBM SKU input → normalized back to FBA anchor price

### Price verification

- Immediate after push: `verify=true` re-reads listing; tolerance `0.01` (`prices_match`)
- Async reflection: up to 30 attempts / 30 minutes → `timeout` or `mismatch`
- Dry-run and failed push → `not_applicable`

### SKU rules vs. app settings vs. localStorage

- UI settings: localStorage + on login merge with DB `app_settings`
- SKU rules override repricer flags **only when field is set** (not `null`)
- Non-admin can change settings in UI → localStorage yes, DB no (403)

### Catalog

- `scan_catalog` without Supabase → JSON cache only in `data/cache/catalog_{CC}.json`
- Cache max 1 hour old unless `refresh`
- FBM detection: SKU suffix `FBM` **or** fulfillment channel `DEFAULT` without Amazon channel

---

## 15. Known Issues / Regression Focus

1. **Repricer/catalog without auth protection** — security-relevant in production
2. **UI does not check role** — admin actions visible to all; API returns 403
3. **SettingsProvider** saves for all users → non-admins see `dbError` (403)
4. **Sales revenue** may always show `€` instead of marketplace currency
5. **QC `run` and `patch_finding`** — no `require_admin`; any authenticated user
6. **First user = admin** — race condition on parallel registration
7. **SP-API rate limits / timeouts** — "Sync all 9" and sales report can take a long time (up to ~10 min)
8. **Sales detail page** has no in-app link from Sales Performance — navigate via URL `/sales/{SKU}` only
9. **`signal_overpriced_low_traffic`** defined in YAML but not implemented in features engine
10. **Edge function cron:** 120s timeout

---

## 16. Test Priorities (Recommended)

| Priority | Area | Why |
|----------|------|-----|
| **P0** | Repricing (dry-run + live), variation/FBM sync, reflection | Core function, direct Amazon impact |
| **P0** | SKU rules (min/max, overrides) | Prevent pricing errors |
| **P1** | Overview KPIs, sales sync + detail, QC dashboard | New release features |
| **P1** | History, catalog sync, multi-marketplace | Data consistency |
| **P1** | Auth/roles (admin vs. user vs. local-dev) | Security |
| **P2** | Features engine, pricing signals | Analytics and monitoring |
| **P2** | Edge cases (FBM SKU input, `double_only`, missing FBM SKU) | Stability |

---

## 17. Glossary

| Term | Meaning |
|------|---------|
| **FBA** | Fulfillment by Amazon |
| **FBM** | Fulfillment by Merchant (merchant-fulfilled) |
| **SKU** | Stock Keeping Unit (Amazon product identifier) |
| **Variation** | Pack-size variant (e.g. single vs. double pack) |
| **Reflection** | Check whether Amazon adopted the set price |
| **Dry-run** | Validation without a real push to Amazon |
| **SP-API** | Amazon Selling Partner API |
| **BFF** | Backend for Frontend — API as the only client entry point |

---

## 18. Summary for the Tester

This app is an **internal Amazon repricing tool** focused on:

1. **Setting prices** with automatic sync to variations and FBM
2. **Verifying** whether Amazon adopted the prices (reflection)
3. **Rules and bounds** per SKU
4. **Overview, sales, catalog, history, and QC** as supporting modules

The most critical path is **Reprice → Preview → Dry-run/Live → History/Reflection**.

**New in this release — test these thoroughly:**

- **Overview dashboard** (`GET /api/overview`) — batched KPIs and QC alert counts
- **Sales performance + detail** — Amazon Sales & Traffic ETL, per-SKU 30-day view
- **QC dashboard** — three automated agents with resolve workflow
- **Multi-marketplace selector** — 9 EU countries with per-country data
- **Auth & roles** — login, admin vs. user permissions

Multi-marketplace behavior, auth roles, and the interaction between SKU rules, app settings, and localStorage remain the most complex areas for edge-case testing.

---

## 19. Key File References

| Area | Path |
|------|------|
| API entry | `api/main.py` |
| Frontend routes | `web/src/App.tsx` |
| Overview API | `api/routes/overview.py` |
| Sales API + ETL | `api/routes/sales.py`, `lib/amazon_reports.py` |
| Sales detail page | `web/src/pages/SalesDetailPage.tsx` |
| Overview page | `web/src/pages/OverviewPage.tsx` |
| QC dashboard | `web/src/pages/QcDashboardPage.tsx`, `lib/qc/runner.py` |
| Marketplace selector | `web/src/components/MarketplaceSelector.tsx`, `lib/marketplaces.py` |
| Price reflection | `lib/price_reflection.py` |
| Features engine | `lib/features_engine.py`, `config/pricing_features.yaml` |
| Repricing logic | `api/routes/repricer.py`, `lib/variations.py`, `lib/fulfillment_pairs.py` |
| Auth | `api/routes/auth.py`, `web/src/components/AuthProvider.tsx` |
| DB schema | `supabase/migrations/` |
| Deployment | `vercel.json` |
