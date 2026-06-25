-- Poll pending price reflections every minute via Repricer API (pg_cron + pg_net).
-- Requires vault secrets: repricer_app_url, catalog_cron_secret (same as CRON_SECRET on Vercel).

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

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
