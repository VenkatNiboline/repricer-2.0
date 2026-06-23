-- sales_with_catalog view + daily sales sync cron

create or replace view public.sales_with_catalog
with (security_invoker = true) as
select
  s.*,
  cat.country as catalog_country,
  cat.sku as catalog_sku,
  cat.price as catalog_price,
  cat.currency as catalog_currency,
  cat.product_name as catalog_product_name
from public.sales_daily s
left join public.sku_catalog cat
  on cat.asin = s.child_asin
  and cat.country = case s.ob_marketplace_id
    when 'A1PA6795UKMFR9' then 'DE'
    when 'A13V1IB3VIYZZH' then 'FR'
    when 'APJ6JRA9NG5V4' then 'IT'
    when 'A1RKKUPIHCS9HS' then 'ES'
    when 'A1805IZSGTT6HS' then 'NL'
    when 'AMEN7PMS3EDWL' then 'BE'
    when 'A1C3SOZRARQ6R3' then 'PL'
    when 'A2NODRKZP88ZB9' then 'SE'
    when 'A1F83G8C2ARO7P' then 'UK'
    else null
  end;

grant select on public.sales_with_catalog to authenticated;

-- Daily sales sync at 06:00 UTC (DE marketplace, 1 day lag)
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
