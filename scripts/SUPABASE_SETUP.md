# Supabase project: amazon-repricer
# Dashboard: https://supabase.com/dashboard/project/mpdhzvklvyzjwxpvsfkw

## Edge Function secrets (Dashboard → Edge Functions → sync-catalog → Secrets)

Required:
- LWA_REFRESH_TOKEN
- LWA_CLIENT_ID
- LWA_CLIENT_SECRET
- SELLER_ID
- CRON_SECRET          (for pg_cron; openssl rand -hex 32)
- SUPABASE_SERVICE_ROLE_KEY  (Dashboard → Settings → API → service_role)

SUPABASE_URL and SUPABASE_ANON_KEY are injected automatically.

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
