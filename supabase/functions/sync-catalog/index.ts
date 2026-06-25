import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { CatalogRow, catalogTableForCountry, getAccessToken, scanAmazonCatalog } from "./amazon.ts";

const BATCH_SIZE = 200;

function unauthorized(message = "Unauthorized") {
  return new Response(JSON.stringify({ error: message }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function authorize(req: Request): Promise<{ ok: boolean; source: string }> {
  const cronSecret = Deno.env.get("CRON_SECRET");
  const providedSecret = req.headers.get("x-cron-secret");
  if (cronSecret && providedSecret === cronSecret) {
    return { ok: true, source: "edge_cron" };
  }

  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return { ok: false, source: "" };
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  if (!supabaseUrl || !anonKey) {
    return { ok: false, source: "" };
  }

  const client = createClient(supabaseUrl, anonKey);
  const token = authHeader.slice(7);
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) return { ok: false, source: "" };
  return { ok: true, source: "edge_ui" };
}

async function upsertCatalogRows(
  supabase: ReturnType<typeof createClient>,
  country: string,
  rows: CatalogRow[],
): Promise<void> {
  const table = catalogTableForCountry(country);
  const now = new Date().toISOString();
  const payload = rows.map((row) => ({
    sku: row.sku,
    asin: row.asin,
    product_name: row.product_name,
    product_type: row.product_type,
    fulfillment: row.fulfillment,
    price: row.price,
    currency: row.currency,
    fba_pair: row.fba_pair,
    is_fbm: row.is_fbm,
    synced_at: now,
  }));

  for (let i = 0; i < payload.length; i += BATCH_SIZE) {
    const batch = payload.slice(i, i + BATCH_SIZE);
    const { error } = await supabase
      .from(table)
      .upsert(batch, { onConflict: "sku" });
    if (error) throw new Error(`Supabase upsert failed (${table}): ${error.message}`);
  }
}

async function recordSyncRun(
  supabase: ReturnType<typeof createClient>,
  country: string,
  skuCount: number,
  source: string,
): Promise<void> {
  const { error } = await supabase.from("catalog_sync_runs").insert({
    country: country.toUpperCase(),
    sku_count: skuCount,
    source,
    completed_at: new Date().toISOString(),
  });
  if (error) throw new Error(`Failed to record sync run: ${error.message}`);
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const auth = await authorize(req);
  if (!auth.ok) {
    return unauthorized("Sign in required or invalid cron secret");
  }

  const sellerId = Deno.env.get("SELLER_ID");
  if (!sellerId) {
    return json({ error: "SELLER_ID secret not configured" }, 500);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json({ error: "SUPABASE_SERVICE_ROLE_KEY not configured" }, 500);
  }

  let country = "DE";
  let region = "EU";
  try {
    const body = await req.json();
    if (body?.country) country = String(body.country).toUpperCase();
    if (body?.region) region = String(body.region).toUpperCase();
  } catch {
    // defaults are fine
  }

  const startedAt = Date.now();

  try {
    const accessToken = await getAccessToken();
    const rows = await scanAmazonCatalog(country, region, sellerId, accessToken);

    const supabase = createClient(supabaseUrl, serviceRoleKey);
    await upsertCatalogRows(supabase, country, rows);
    await recordSyncRun(supabase, country, rows.length, auth.source);

    const fba = rows.filter((r) => r.fulfillment === "FBA").length;
    const fbm = rows.filter((r) => r.fulfillment === "FBM").length;
    const fbmSuffix = rows.filter((r) => r.is_fbm).length;
    const syncedAt = new Date().toISOString();

    return json({
      ok: true,
      country,
      region,
      source: auth.source,
      count: rows.length,
      stats: {
        total: rows.length,
        fba,
        fbm,
        fbm_suffix: fbmSuffix,
        synced_at: syncedAt,
        source: "supabase",
      },
      duration_ms: Date.now() - startedAt,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return json({ ok: false, error: message, duration_ms: Date.now() - startedAt }, 500);
  }
});
