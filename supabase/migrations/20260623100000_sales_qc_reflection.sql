-- Sales, QC, and price reflection status

-- Price history reflection tracking
alter table public.price_history
  add column if not exists reflection_status text not null default 'not_applicable'
    check (reflection_status in (
      'pending', 'reflected', 'mismatch', 'timeout', 'not_applicable'
    )),
  add column if not exists reflection_checked_at timestamptz,
  add column if not exists reflection_attempts int not null default 0;

-- QC runs and findings
create table if not exists public.qc_runs (
  id bigint generated always as identity primary key,
  agent_name text not null,
  status text not null default 'running' check (status in ('running', 'completed', 'failed')),
  summary text,
  findings_count int not null default 0,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.qc_findings (
  id bigint generated always as identity primary key,
  qc_run_id bigint references public.qc_runs (id) on delete set null,
  agent_name text not null,
  check_id text not null,
  severity text not null default 'info' check (severity in ('critical', 'warning', 'info')),
  sku text,
  country text,
  asin text,
  message text not null,
  metadata jsonb,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_qc_findings_open on public.qc_findings (resolved, severity, created_at desc);
create index if not exists idx_qc_findings_sku on public.qc_findings (sku, country);

-- Sales daily (matches GET_SALES_AND_TRAFFIC_REPORT schema)
create table if not exists public.sales_daily (
  id bigint generated always as identity primary key,
  ob_marketplace_id text not null,
  ob_seller_id text not null,
  child_asin text not null,
  parent_asin text,
  sku text,
  ordered_product_sales_amount numeric(14, 2),
  ordered_product_sales_currency_code text,
  ordered_product_sales_b2_b_amount numeric(14, 2),
  ordered_product_sales_b2_b_currency_code text,
  total_order_items int,
  total_order_items_b2_b int,
  units_ordered int,
  units_ordered_b2_b int,
  browser_page_views int,
  browser_page_views_b2_b int,
  browser_page_views_percentage numeric(8, 4),
  browser_page_views_percentage_b2_b numeric(8, 4),
  browser_session_percentage numeric(8, 4),
  browser_session_percentage_b2_b numeric(8, 4),
  browser_sessions int,
  browser_sessions_b2_b int,
  buy_box_percentage numeric(8, 4),
  buy_box_percentage_b2_b numeric(8, 4),
  mobile_app_page_views int,
  mobile_app_page_views_b2_b int,
  mobile_app_page_views_percentage numeric(8, 4),
  mobile_app_page_views_percentage_b2_b numeric(8, 4),
  mobile_app_session_percentage numeric(8, 4),
  mobile_app_session_percentage_b2_b numeric(8, 4),
  mobile_app_sessions int,
  mobile_app_sessions_b2_b int,
  page_views int,
  page_views_b2_b int,
  page_views_percentage numeric(8, 4),
  page_views_percentage_b2_b numeric(8, 4),
  session_percentage numeric(8, 4),
  session_percentage_b2_b numeric(8, 4),
  sessions int,
  sessions_b2_b int,
  unit_session_percentage numeric(8, 4),
  unit_session_percentage_b2_b numeric(8, 4),
  ob_date date not null,
  ob_transaction_id text,
  ob_file_name text,
  ob_processed_at text,
  ob_modified_date timestamptz,
  unique (ob_marketplace_id, child_asin, ob_date)
);

create index if not exists idx_sales_daily_date on public.sales_daily (ob_date desc);
create index if not exists idx_sales_daily_asin on public.sales_daily (child_asin, ob_date);
create index if not exists idx_sales_daily_sku on public.sales_daily (sku, ob_date) where sku is not null;

create table if not exists public.sales_sync_runs (
  id bigint generated always as identity primary key,
  country text not null,
  date_start date,
  date_end date,
  row_count int not null default 0,
  status text not null default 'running',
  error text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_by uuid references public.profiles (id)
);

create table if not exists public.pricing_features_daily (
  id bigint generated always as identity primary key,
  sku text not null,
  country text not null,
  feature_date date not null,
  feature_id text not null,
  feature_value numeric(14, 4),
  metadata jsonb,
  computed_at timestamptz not null default now(),
  unique (sku, country, feature_date, feature_id)
);

-- RLS
alter table public.qc_runs enable row level security;
alter table public.qc_findings enable row level security;
alter table public.sales_daily enable row level security;
alter table public.sales_sync_runs enable row level security;
alter table public.pricing_features_daily enable row level security;

create policy qc_runs_select_auth on public.qc_runs
for select to authenticated using (true);

create policy qc_findings_select_auth on public.qc_findings
for select to authenticated using (true);

create policy qc_findings_update_auth on public.qc_findings
for update to authenticated using (true) with check (true);

create policy sales_daily_select_auth on public.sales_daily
for select to authenticated using (true);

create policy sales_sync_runs_select_auth on public.sales_sync_runs
for select to authenticated using (true);

create policy pricing_features_select_auth on public.pricing_features_daily
for select to authenticated using (true);

grant select on public.qc_runs to authenticated;
grant select, update on public.qc_findings to authenticated;
grant select on public.sales_daily to authenticated;
grant select on public.sales_sync_runs to authenticated;
grant select on public.pricing_features_daily to authenticated;
