-- Tighten price_history inserts and lock down handle_new_user RPC access.

drop policy if exists history_insert_auth on public.price_history;

create policy history_insert_auth on public.price_history
for insert to authenticated
with check (created_by = auth.uid());

revoke all on function public.handle_new_user() from public;
revoke all on function public.handle_new_user() from anon, authenticated;
