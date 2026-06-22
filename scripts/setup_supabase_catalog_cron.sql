-- One-time setup for automatic catalog sync
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/mpdhzvklvyzjwxpvsfkw/sql

-- Step 1: Vault secrets for pg_cron HTTP calls
select vault.create_secret(
  'https://mpdhzvklvyzjwxpvsfkw.supabase.co',
  'project_url',
  'Repricer project URL for catalog cron'
);

-- Replace the value below with your own secret (openssl rand -hex 32)
-- Must match Edge Function secret CRON_SECRET exactly.
select vault.create_secret(
  'REPLACE_WITH_YOUR_CRON_SECRET',
  'catalog_cron_secret',
  'Auth header for sync-catalog edge function'
);

-- Step 2: Edge Function secrets (Dashboard → Edge Functions → sync-catalog → Secrets)
--   LWA_REFRESH_TOKEN   (from ENV/AmazonCredentials.env)
--   LWA_CLIENT_ID
--   LWA_CLIENT_SECRET
--   SELLER_ID
--   CRON_SECRET         (same value as catalog_cron_secret above)
--
-- SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are injected automatically.

-- Step 3: Verify cron job
-- select jobid, jobname, schedule, active from cron.job where jobname = 'sync-amazon-catalog';

-- Step 4: Manual test (replace YOUR_CRON_SECRET)
-- select net.http_post(
--   url := 'https://mpdhzvklvyzjwxpvsfkw.supabase.co/functions/v1/sync-catalog',
--   headers := jsonb_build_object(
--     'Content-Type', 'application/json',
--     'x-cron-secret', 'YOUR_CRON_SECRET'
--   ),
--   body := '{"country":"DE","region":"EU"}'::jsonb,
--   timeout_milliseconds := 120000
-- );

-- Step 5: Check results
-- select * from catalog_sync_runs order by completed_at desc limit 5;
-- select count(*) from sku_catalog where country = 'DE';
