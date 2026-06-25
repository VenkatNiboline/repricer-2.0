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

## 2. Architecture (High-Level)

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

## 3. User Roles and Authentication

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

## 4. Pages and Features

| Route | Page | Function |
|-------|------|----------|
| `/` | Overview | Dashboard: catalog stats, sync single/all 9 EU marketplaces, API health |
| `/catalog` | SKU Catalog | Full catalog with search, FBA/FBM filter, sync, CSV export |
| `/reprice` | Reprice | **Core workflow:** SKU + price → preview → dry-run or live push to Amazon |
| `/sales` | Sales | 7-day revenue/units, manual sales sync (admin) |
| `/rules` | SKU Rules | Min/max, FBM discount, sync flags per SKU (admin writes) |
| `/history` | History | Price history with reflection status, manual re-verify |
| `/qc` | QC Dashboard | Open findings, run QC, resolve findings |
| `/fbm` | FBM Catalog | FBM SKUs only, CSV export |
| `/settings` | Settings | Marketplace, region, sync flags, FBM discount, dry-run default |

**Global marketplace selector** in the header controls `settings.country` for nearly all pages.

**Auth gate:** When `SUPABASE_URL` + `SUPABASE_ANON_KEY` are set → login required. Without auth → app runs in open local-dev mode.

---

## 5. Critical Business Rules

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

## 6. Core Workflows (Test Priority)

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

### E. Sales

- Summary: 7-day revenue/units
- Admin: sales sync → Amazon report (poll up to ~10 min), upsert `sales_daily`, features engine, QC

### F. QC

- **repricing_qc:** stale pending (>30 min), mismatch, timeout, push_failed
- **data_qc:** missing/stale sales data (>2 days)
- **pricing_qc:** `signal_underpriced_high_demand` (units ≥ 10, buy_box ≥ 90%)
- Resolve findings via PATCH

---

## 7. Multi-Marketplace Support

**9 EU marketplaces:** `DE`, `FR`, `IT`, `ES`, `NL`, `BE`, `PL` (PLN), `SE` (SEK), `UK` (GBP)

- Separate DB table per country: `sku_catalog_de`, `sku_catalog_fr`, …
- **Cron sync is DE only** (every 6 hours) — other countries require manual sync (UI "Sync all 9" or API)
- Currency per country in API; sales page may show revenue hardcoded as `€` — possible display bug for UK/PL/SE

---

## 8. API Overview

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

## 9. Data Model (Key Entities)

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

## 10. External Integrations

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

## 11. Background Jobs and Scripts

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

## 12. Test Environment Setup

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

## 13. Edge Cases and Complex Logic

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

## 14. Known Issues / Regression Focus

1. **Repricer/catalog without auth protection** — security-relevant in production
2. **UI does not check role** — admin actions visible to all; API returns 403
3. **SettingsProvider** saves for all users → non-admins see `dbError` (403)
4. **Sales revenue** may always show `€` instead of marketplace currency
5. **QC `run` and `patch_finding`** — no `require_admin`; any authenticated user
6. **First user = admin** — race condition on parallel registration
7. **SP-API rate limits / timeouts** — "Sync all 9" and sales report can take a long time (up to ~10 min)
8. **Edge function cron:** 120s timeout

---

## 15. Test Priorities (Recommended)

| Priority | Area | Why |
|----------|------|-----|
| **P0** | Repricing (dry-run + live), variation/FBM sync, reflection | Core function, direct Amazon impact |
| **P0** | SKU rules (min/max, overrides) | Prevent pricing errors |
| **P1** | History, catalog sync, multi-marketplace | Data consistency |
| **P1** | Auth/roles (admin vs. user vs. local-dev) | Security |
| **P2** | Sales, QC, features engine | Analytics and monitoring |
| **P2** | Edge cases (FBM SKU input, `double_only`, missing FBM SKU) | Stability |

---

## 16. Glossary

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

## 17. Summary for the Tester

This app is an **internal Amazon repricing tool** focused on:

1. **Setting prices** with automatic sync to variations and FBM
2. **Verifying** whether Amazon adopted the prices
3. **Rules and bounds** per SKU
4. **Catalog, history, sales, and QC** as supporting modules

The most critical path is **Reprice → Preview → Dry-run/Live → History/Reflection**. Multi-marketplace behavior, auth roles, and the interaction between SKU rules, app settings, and localStorage are the most complex areas for edge-case testing.

---

## 18. Key File References

| Area | Path |
|------|------|
| API entry | `api/main.py` |
| Frontend routes | `web/src/App.tsx` |
| Repricing logic | `api/routes/repricer.py`, `lib/variations.py`, `lib/fulfillment_pairs.py` |
| DB schema | `supabase/migrations/` |
| Deployment | `vercel.json` |
| Pricing features config | `config/pricing_features.yaml` |
