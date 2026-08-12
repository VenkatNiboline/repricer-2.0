-- Re-enable scheduled jobs that call Amazon SP-API (catalog sync, sales ETL, price reflection).
-- Run after AMAZON_API_ENABLED=true and vault secrets are configured.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

-- Catalog sync: every 6 hours at :15 UTC
do $$
declare
  job record;
begin
  for job in select jobid from cron.job where jobname = 'sync-amazon-catalog' loop
    perform cron.unschedule(job.jobid);
  end loop;
end $$;

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

-- Sales sync: daily at 06:00 UTC
do $$
declare
  job record;
begin
  for job in select jobid from cron.job where jobname = 'sync-amazon-sales' loop
    perform cron.unschedule(job.jobid);
  end loop;
end $$;

select cron.schedule(
  'sync-amazon-sales',
  '0 6 * * *',
  $$
  select net.http_post(
    url := coalesce(
      (select decrypted_secret from vault.decrypted_secrets where name = 'project_url' limit 1),
      'https://mpdhzvklvyzjwxpvsfkw.supabase.co'
    ) || '/functions/v1/sync-sales',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', coalesce(
        (select decrypted_secret from vault.decrypted_secrets where name = 'catalog_cron_secret' limit 1),
        ''
      )
    ),
    body := '{"country":"DE","region":"EU","days":1}'::jsonb,
    timeout_milliseconds := 600000
  ) as request_id;
  $$
);

-- Price reflection poll: every minute
do $$
declare
  job record;
begin
  for job in select jobid from cron.job where jobname = 'verify-price-reflections' loop
    perform cron.unschedule(job.jobid);
  end loop;
end $$;

select cron.schedule(
  'verify-price-reflections',
  '* * * * *',
  $$
  select net.http_get(
    url := coalesce(
      (select decrypted_secret from vault.decrypted_secrets where name = 'repricer_app_url' limit 1),
      'https://repricer-2-0.vercel.app'
    ) || '/api/history/verify-pending-cron',
    headers := jsonb_build_object(
      'x-cron-secret', coalesce(
        (select decrypted_secret from vault.decrypted_secrets where name = 'catalog_cron_secret' limit 1),
        ''
      )
    ),
    timeout_milliseconds := 120000
  ) as request_id;
  $$
);
