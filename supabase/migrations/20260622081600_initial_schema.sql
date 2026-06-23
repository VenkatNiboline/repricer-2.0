-- Amazon Repricer initial schema

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text,
  role text not null default 'user' check (role in ('admin', 'user')),
  created_at timestamptz not null default now()
);

create table public.app_settings (
  id int primary key default 1 check (id = 1),
  default_country text not null default 'DE',
  default_region text not null default 'EU',
  default_fbm_discount numeric(5, 4) not null default 0.10,
  sync_siblings boolean not null default true,
  sync_fbm boolean not null default true,
  updated_at timestamptz not null default now()
);

insert into public.app_settings (id) values (1);

create table public.sku_catalog (
  id bigint generated always as identity primary key,
  sku text not null,
  country text not null,
  asin text,
  product_type text,
  fulfillment text not null,
  price numeric(12, 2),
  currency text not null default 'EUR',
  fba_pair text,
  is_fbm boolean not null default false,
  parent_sku text,
  size_label text,
  units numeric(12, 2),
  synced_at timestamptz not null default now(),
  unique (sku, country)
);

create index idx_sku_catalog_country on public.sku_catalog (country);
create index idx_sku_catalog_fulfillment on public.sku_catalog (fulfillment);
create index idx_sku_catalog_parent on public.sku_catalog (parent_sku);

create table public.catalog_sync_runs (
  id bigint generated always as identity primary key,
  country text not null,
  sku_count int not null default 0,
  source text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_by uuid references public.profiles (id)
);

create table public.sku_rules (
  id bigint generated always as identity primary key,
  sku text not null,
  country text not null,
  min_price numeric(12, 2),
  max_price numeric(12, 2),
  fbm_discount numeric(5, 4),
  sync_siblings boolean,
  sync_fbm boolean,
  notes text,
  updated_by uuid references public.profiles (id),
  updated_at timestamptz not null default now(),
  unique (sku, country)
);

create table public.price_history (
  id bigint generated always as identity primary key,
  sku text not null,
  country text not null,
  old_price numeric(12, 2),
  new_price numeric(12, 2) not null,
  currency text not null,
  link_kind text not null default 'primary',
  parent_sku text,
  dry_run boolean not null default false,
  validation_ok boolean,
  pushed boolean not null default false,
  submission_id text,
  verified_price numeric(12, 2),
  error text,
  created_by uuid references public.profiles (id),
  created_at timestamptz not null default now()
);

create index idx_price_history_sku on public.price_history (sku, country);
create index idx_price_history_created on public.price_history (created_at desc);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    case when (select count(*) from public.profiles) = 0 then 'admin' else 'user' end
  );
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

revoke all on function public.handle_new_user() from public;
revoke all on function public.handle_new_user() from anon, authenticated;

alter table public.profiles enable row level security;
alter table public.app_settings enable row level security;
alter table public.sku_catalog enable row level security;
alter table public.catalog_sync_runs enable row level security;
alter table public.sku_rules enable row level security;
alter table public.price_history enable row level security;

create policy profiles_select_own on public.profiles
for select to authenticated using (auth.uid() = id);

create policy profiles_select_admin on public.profiles
for select to authenticated using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);

create policy catalog_select_auth on public.sku_catalog
for select to authenticated using (true);

create policy history_select_auth on public.price_history
for select to authenticated using (true);

create policy rules_select_auth on public.sku_rules
for select to authenticated using (true);

create policy settings_select_auth on public.app_settings
for select to authenticated using (true);

create policy sync_runs_select_auth on public.catalog_sync_runs
for select to authenticated using (true);

create policy rules_admin_all on public.sku_rules
for all to authenticated using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
) with check (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);

create policy settings_admin_update on public.app_settings
for update to authenticated using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);
