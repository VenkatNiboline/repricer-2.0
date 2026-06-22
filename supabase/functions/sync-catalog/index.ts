import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { CatalogRow, getAccessToken, scanAmazonCatalog } from "./amazon.ts";

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

async function upsertCatalogRows(
  supabase: ReturnType<typeof createClient>,
  country: string,
  rows: CatalogRow[],
): Promise<void> {
  const now = new Date().toISOString();
  const payload = rows.map((row) => ({
    sku: row.sku,
    country: country.toUpperCase(),
    asin: row.asin,
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
      .from("sku_catalog")
      .upsert(batch, { onConflict: "sku,country" });
    if (error) throw new Error(`Supabase upsert failed: ${error.message}`);
  }
}

async function recordSyncRun(
  supabase: ReturnType<typeof createClient>,
  country: string,
  skuCount: number,
): Promise<void> {
  const { error } = await supabase.from("catalog_sync_runs").insert({
    country: country.toUpperCase(),
    sku_count: skuCount,
    source: "edge_cron",
    completed_at: new Date().toISOString(),
  });
  if (error) throw new Error(`Failed to record sync run: ${error.message}`);
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const cronSecret = Deno.env.get("CRON_SECRET");
  const providedSecret = req.headers.get("x-cron-secret");
  if (!cronSecret || providedSecret !== cronSecret) {
    return unauthorized("Invalid or missing x-cron-secret");
  }

  const sellerId = Deno.env.get("SELLER_ID");
  if (!sellerId) {
    return json({ error: "SELLER_ID secret not configured" }, 500);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json({ error: "Supabase env not configured" }, 500);
  }

  let country = "DE";
  let region = "EU";
  try {
    const body = await req.json();
    if (body?.country) country = String(body.country).toUpperCase();
    if (body?.region) region = String(body.region).toUpperCase();
  } catch {
    // empty body is fine — use defaults
  }

  const startedAt = Date.now();

  try {
    const accessToken = await getAccessToken();
    const rows = await scanAmazonCatalog(country, region, sellerId, accessToken);

    const supabase = createClient(supabaseUrl, serviceRoleKey);
    await upsertCatalogRows(supabase, country, rows);
    await recordSyncRun(supabase, country, rows.length);

    const fba = rows.filter((r) => r.fulfillment === "FBA").length;
    const fbm = rows.filter((r) => r.fulfillment === "FBM").length;
    const fbmSuffix = rows.filter((r) => r.is_fbm).length;

    return json({
      ok: true,
      country,
      region,
      source: "edge_cron",
      count: rows.length,
      stats: {
        total: rows.length,
        fba,
        fbm,
        fbm_suffix: fbmSuffix,
        synced_at: new Date().toISOString(),
      },
      duration_ms: Date.now() - startedAt,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return json({ ok: false, error: message, duration_ms: Date.now() - startedAt }, 500);
  }
});
