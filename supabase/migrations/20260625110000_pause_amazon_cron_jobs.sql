-- Pause scheduled jobs that call Amazon SP-API (catalog sync, sales ETL, price reflection).
-- Re-enable by re-running the original schedule migrations or setting AMAZON_API_ENABLED=true
-- and restoring cron jobs manually.

do $$
declare
  job record;
begin
  for job in
    select jobid
    from cron.job
    where jobname in (
      'sync-amazon-catalog',
      'sync-amazon-sales',
      'verify-price-reflections'
    )
  loop
    perform cron.unschedule(job.jobid);
  end loop;
end $$;
