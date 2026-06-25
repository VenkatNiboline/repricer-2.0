import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { fetchSalesReport } from "./reports.ts";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function amazonApiEnabled(): boolean {
  const raw = (Deno.env.get("AMAZON_API_ENABLED") ?? "true").trim().toLowerCase();
  return !["false", "0", "no", "off"].includes(raw);
}

async function authorize(req: Request): Promise<boolean> {
  const cronSecret = Deno.env.get("CRON_SECRET");
  const provided = req.headers.get("x-cron-secret");
  if (cronSecret && provided === cronSecret) return true;

  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return false;
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  if (!supabaseUrl || !anonKey) return false;
  const client = createClient(supabaseUrl, anonKey);
  const { data, error } = await client.auth.getUser(authHeader.slice(7));
  return !error && !!data.user;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }
  if (!(await authorize(req))) {
    return json({ error: "Unauthorized" }, 401);
  }
  if (!amazonApiEnabled()) {
    return json(
      { ok: false, error: "Amazon SP-API access is disabled (AMAZON_API_ENABLED=false)" },
      503,
    );
  }

  let body: { country?: string; days?: number } = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  const country = (body.country ?? "DE").toUpperCase();
  const days = Math.max(1, Math.min(body.days ?? 1, 30));

  const end = new Date();
  end.setUTCDate(end.getUTCDate() - 1);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - (days - 1));
  const fmt = (d: Date) => d.toISOString().slice(0, 10);

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) {
    return json({ error: "Supabase not configured" }, 500);
  }

  try {
    const rows = await fetchSalesReport(country, fmt(start), fmt(end));
    const supabase = createClient(supabaseUrl, serviceKey);
    const batchSize = 200;
    for (let i = 0; i < rows.length; i += batchSize) {
      const batch = rows.slice(i, i + batchSize);
      const { error } = await supabase
        .from("sales_daily")
        .upsert(batch, { onConflict: "ob_marketplace_id,child_asin,ob_date" });
      if (error) throw error;
    }
    await supabase.from("sales_sync_runs").insert({
      country,
      date_start: fmt(start),
      date_end: fmt(end),
      row_count: rows.length,
      status: "completed",
      completed_at: new Date().toISOString(),
    });
    return json({ ok: true, country, rows: rows.length });
  } catch (err) {
    return json({ ok: false, error: String(err) }, 500);
  }
});
