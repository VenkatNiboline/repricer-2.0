# Supabase project: amazon-repricer
# Dashboard: https://supabase.com/dashboard/project/mpdhzvklvyzjwxpvsfkw

## Go live

1. Ensure the Supabase project is **Active** (not paused) in the dashboard.
2. Set `AMAZON_API_ENABLED=true` and fill `SUPABASE_SERVICE_ROLE_KEY` in `ENV/AmazonCredentials.env`.
3. Run `./scripts/activate_live.sh` (requires `npx vercel login` once).
4. In Supabase → Edge Functions → Secrets, set `AMAZON_API_ENABLED=true` and `CRON_SECRET` (same as env file).
5. Verify: `curl https://repricer-2-0.vercel.app/api/health` → `amazon_api_enabled: true`, `db_write_ready: true`.

Cron jobs (re-enabled by migration `20260625120000_resume_amazon_cron_jobs.sql`):

| Job | Schedule | Purpose |
|-----|----------|---------|
| `sync-amazon-catalog` | Every 6h at :15 UTC | DE catalog from Amazon |
| `sync-amazon-sales` | Daily 06:00 UTC | Sales & Traffic ETL |
| `verify-price-reflections` | Every minute | Poll pending price reflections |

## Edge Function secrets (Dashboard → Edge Functions → Secrets)

Applies to **sync-catalog** and **sync-sales**:

- LWA_REFRESH_TOKEN
- LWA_CLIENT_ID
- LWA_CLIENT_SECRET
- SELLER_ID
- CRON_SECRET — must match vault `catalog_cron_secret` (see `scripts/setup_supabase_catalog_cron.sql`)

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically for Edge Functions.

Also set `SUPABASE_SERVICE_ROLE_KEY` and `CRON_SECRET` on **Vercel** (run `scripts/sync_vercel_env.sh` after filling `ENV/AmazonCredentials.env`).

## How it works

1. **sync-catalog** Edge Function fetches SKUs from Amazon SP-API
2. Writes to **sku_catalog** table in Supabase
3. **UI** reads directly from Supabase (no Python API needed for catalog)
4. **pg_cron** runs sync every 6 hours automatically

## Trigger sync from UI

Sign in → Overview or SKU Catalog → **Sync catalog**

## Verify data

```sql
select count(*) from sku_catalog;
select * from catalog_sync_runs order by completed_at desc limit 5;
```
