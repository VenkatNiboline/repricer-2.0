-- Allow authenticated users to insert their own price history rows.
create policy history_insert_auth on public.price_history
for insert to authenticated
with check (created_by = auth.uid());
