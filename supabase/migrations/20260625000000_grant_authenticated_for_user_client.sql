-- Grants for the authenticated role so request-scoped (user-JWT) clients can reach
-- the existing RLS policies. The API now queries as the caller instead of with the
-- service-role key, so PostgREST must allow the authenticated role at the table level;
-- RLS still constrains which rows. Supabase grants these by default — this makes the
-- dependency explicit and guarantees it across environments. Grants are idempotent.

grant select, insert on public.price_history to authenticated;
grant select, insert, update, delete on public.sku_rules to authenticated;
grant select, update on public.app_settings to authenticated;
grant select on public.profiles to authenticated;
