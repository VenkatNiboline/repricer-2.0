-- Fix Supabase linter: public.sku_catalog must use SECURITY INVOKER so RLS
-- on the underlying sku_catalog_* tables applies to the querying user.

alter view public.sku_catalog set (security_invoker = true);
