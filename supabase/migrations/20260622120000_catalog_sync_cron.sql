-- Scheduled catalog sync via pg_cron → Edge Function sync-catalog
-- Requires vault secrets: project_url, catalog_cron_secret (see scripts/setup_supabase_catalog_cron.sql)

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

-- Remove previous schedule if re-running migration
do $$
declare
  job record;
begin
  for job in select jobid from cron.job where jobname = 'sync-amazon-catalog' loop
    perform cron.unschedule(job.jobid);
  end loop;
end $$;

-- Every 6 hours at :15 (UTC) — ~889 SKUs, safe for SP-API rate limits
select cron.schedule(
  'sync-amazon-catalog',
  '15 */6 * * *',
  $$
  select net.http_post(
    url := coalesce(
      (select decrypted_secret from vault.decrypted_secrets where name = 'project_url' limit 1),
      'https://mpdhzvklvyzjwxpvsfkw.supabase.co'
    ) || '/functions/v1/sync-catalog',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', coalesce(
        (select decrypted_secret from vault.decrypted_secrets where name = 'catalog_cron_secret' limit 1),
        ''
      )
    ),
    body := '{"country":"DE","region":"EU"}'::jsonb,
    timeout_milliseconds := 120000
  ) as request_id;
  $$
);
