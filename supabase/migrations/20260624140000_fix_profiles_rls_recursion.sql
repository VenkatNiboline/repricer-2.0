-- Fix infinite recursion: admin policies must not SELECT from profiles inside profiles RLS.
-- Use a SECURITY DEFINER helper instead.

create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to authenticated;

drop policy if exists profiles_select_admin on public.profiles;
create policy profiles_select_admin on public.profiles
for select to authenticated
using (public.is_admin());

drop policy if exists rules_admin_all on public.sku_rules;
create policy rules_admin_all on public.sku_rules
for all to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists settings_admin_update on public.app_settings;
create policy settings_admin_update on public.app_settings
for update to authenticated
using (public.is_admin());
