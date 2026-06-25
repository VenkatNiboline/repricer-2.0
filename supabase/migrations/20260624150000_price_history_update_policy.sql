-- Allow reflection status updates on price_history (cron + manual re-check).

create policy history_update_auth on public.price_history
for update to authenticated
using (true)
with check (true);
