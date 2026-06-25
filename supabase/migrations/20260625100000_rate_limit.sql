-- Shared rate-limit store for serverless API instances (service role only).

create table public.rate_limit_hits (
  id bigint generated always as identity primary key,
  rate_key text not null,
  hit_at timestamptz not null default now()
);

create index idx_rate_limit_hits_key_time on public.rate_limit_hits (rate_key, hit_at desc);

alter table public.rate_limit_hits enable row level security;

-- No policies: only service role (bypasses RLS) may access this table.

create or replace function public.rate_limit_check(
  p_key text,
  p_max int,
  p_window_secs int
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count int;
  v_cutoff timestamptz;
begin
  v_cutoff := now() - make_interval(secs => p_window_secs);

  delete from public.rate_limit_hits
  where rate_key = p_key and hit_at < v_cutoff;

  select count(*)::int into v_count
  from public.rate_limit_hits
  where rate_key = p_key and hit_at >= v_cutoff;

  if v_count >= p_max then
    return false;
  end if;

  insert into public.rate_limit_hits (rate_key, hit_at) values (p_key, now());
  return true;
end;
$$;

revoke all on function public.rate_limit_check(text, int, int) from public;
revoke all on function public.rate_limit_check(text, int, int) from anon, authenticated;
