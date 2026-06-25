-- Per-marketplace catalog tables (EU-9) + product_name + unified read view

create table if not exists public.sku_catalog_de (
  id bigint generated always as identity primary key,
  sku text not null unique,
  asin text,
  product_name text,
  product_type text,
  fulfillment text not null,
  price numeric(12, 2),
  currency text not null default 'EUR',
  fba_pair text,
  is_fbm boolean not null default false,
  parent_sku text,
  size_label text,
  units numeric(12, 2),
  synced_at timestamptz not null default now()
);

create table if not exists public.sku_catalog_fr (
  like public.sku_catalog_de including all
);

create table if not exists public.sku_catalog_it (
  like public.sku_catalog_de including all
);

create table if not exists public.sku_catalog_es (
  like public.sku_catalog_de including all
);

create table if not exists public.sku_catalog_nl (
  like public.sku_catalog_de including all
);

create table if not exists public.sku_catalog_be (
  like public.sku_catalog_de including all
);

create table if not exists public.sku_catalog_pl (
  like public.sku_catalog_de including all including defaults
);
alter table public.sku_catalog_pl alter column currency set default 'PLN';

create table if not exists public.sku_catalog_se (
  like public.sku_catalog_de including all including defaults
);
alter table public.sku_catalog_se alter column currency set default 'SEK';

create table if not exists public.sku_catalog_uk (
  like public.sku_catalog_de including all including defaults
);
alter table public.sku_catalog_uk alter column currency set default 'GBP';

create index if not exists idx_sku_catalog_de_fulfillment on public.sku_catalog_de (fulfillment);
create index if not exists idx_sku_catalog_fr_fulfillment on public.sku_catalog_fr (fulfillment);
create index if not exists idx_sku_catalog_it_fulfillment on public.sku_catalog_it (fulfillment);
create index if not exists idx_sku_catalog_es_fulfillment on public.sku_catalog_es (fulfillment);
create index if not exists idx_sku_catalog_nl_fulfillment on public.sku_catalog_nl (fulfillment);
create index if not exists idx_sku_catalog_be_fulfillment on public.sku_catalog_be (fulfillment);
create index if not exists idx_sku_catalog_pl_fulfillment on public.sku_catalog_pl (fulfillment);
create index if not exists idx_sku_catalog_se_fulfillment on public.sku_catalog_se (fulfillment);
create index if not exists idx_sku_catalog_uk_fulfillment on public.sku_catalog_uk (fulfillment);

-- Migrate existing DE rows from legacy unified table
insert into public.sku_catalog_de (
  sku, asin, product_name, product_type, fulfillment, price, currency,
  fba_pair, is_fbm, parent_sku, size_label, units, synced_at
)
select
  sku, asin, null, product_type, fulfillment, price, currency,
  fba_pair, is_fbm, parent_sku, size_label, units, synced_at
from public.sku_catalog
where country = 'DE'
on conflict (sku) do update set
  asin = excluded.asin,
  product_type = excluded.product_type,
  fulfillment = excluded.fulfillment,
  price = excluded.price,
  currency = excluded.currency,
  fba_pair = excluded.fba_pair,
  is_fbm = excluded.is_fbm,
  parent_sku = excluded.parent_sku,
  size_label = excluded.size_label,
  units = excluded.units,
  synced_at = excluded.synced_at;

drop policy if exists catalog_select_auth on public.sku_catalog;
drop table if exists public.sku_catalog;

create or replace view public.sku_catalog
with (security_invoker = true) as
  select 'DE'::text as country, * from public.sku_catalog_de
  union all select 'FR', * from public.sku_catalog_fr
  union all select 'IT', * from public.sku_catalog_it
  union all select 'ES', * from public.sku_catalog_es
  union all select 'NL', * from public.sku_catalog_nl
  union all select 'BE', * from public.sku_catalog_be
  union all select 'PL', * from public.sku_catalog_pl
  union all select 'SE', * from public.sku_catalog_se
  union all select 'UK', * from public.sku_catalog_uk;

alter table public.sku_catalog_de enable row level security;
alter table public.sku_catalog_fr enable row level security;
alter table public.sku_catalog_it enable row level security;
alter table public.sku_catalog_es enable row level security;
alter table public.sku_catalog_nl enable row level security;
alter table public.sku_catalog_be enable row level security;
alter table public.sku_catalog_pl enable row level security;
alter table public.sku_catalog_se enable row level security;
alter table public.sku_catalog_uk enable row level security;

create policy catalog_de_select_auth on public.sku_catalog_de for select to authenticated using (true);
create policy catalog_fr_select_auth on public.sku_catalog_fr for select to authenticated using (true);
create policy catalog_it_select_auth on public.sku_catalog_it for select to authenticated using (true);
create policy catalog_es_select_auth on public.sku_catalog_es for select to authenticated using (true);
create policy catalog_nl_select_auth on public.sku_catalog_nl for select to authenticated using (true);
create policy catalog_be_select_auth on public.sku_catalog_be for select to authenticated using (true);
create policy catalog_pl_select_auth on public.sku_catalog_pl for select to authenticated using (true);
create policy catalog_se_select_auth on public.sku_catalog_se for select to authenticated using (true);
create policy catalog_uk_select_auth on public.sku_catalog_uk for select to authenticated using (true);

grant select on public.sku_catalog to authenticated;
grant select on public.sku_catalog_de to authenticated;
grant select on public.sku_catalog_fr to authenticated;
grant select on public.sku_catalog_it to authenticated;
grant select on public.sku_catalog_es to authenticated;
grant select on public.sku_catalog_nl to authenticated;
grant select on public.sku_catalog_be to authenticated;
grant select on public.sku_catalog_pl to authenticated;
grant select on public.sku_catalog_se to authenticated;
grant select on public.sku_catalog_uk to authenticated;
