const MARKETPLACE_IDS: Record<string, string> = {
  DE: "A1PA6795UKMFR9",
  FR: "A13V1IB3VIYZZH",
  IT: "APJ6JRA9NG5V4",
  ES: "A1RKKUPIHCS9HS",
  NL: "A1805IZSGTT6HS",
  BE: "AMEN7PMS3EDWL",
  PL: "A1C3SOZRARQ6R3",
  SE: "A2NODRKZP88ZB9",
  UK: "A1F83G8C2ARO7P",
};

const SP_API_BASE = "https://sellingpartnerapi-eu.amazon.com";
const REPORT_TYPE = "GET_SALES_AND_TRAFFIC_REPORT";

export function marketplaceId(country: string): string {
  const id = MARKETPLACE_IDS[country.toUpperCase()];
  if (!id) throw new Error(`Unknown country: ${country}`);
  return id;
}

export async function getAccessToken(): Promise<string> {
  const clientId = Deno.env.get("LWA_CLIENT_ID");
  const clientSecret = Deno.env.get("LWA_CLIENT_SECRET");
  const refreshToken = Deno.env.get("LWA_REFRESH_TOKEN");
  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error("Missing LWA credentials");
  }
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: clientId,
    client_secret: clientSecret,
  });
  const res = await fetch("https://api.amazon.com/auth/o2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error(`Token error: ${await res.text()}`);
  const data = await res.json();
  if (!data.access_token) throw new Error("No access_token");
  return data.access_token as string;
}

function authHeaders(token: string): HeadersInit {
  return { "x-amz-access-token": token, "Content-Type": "application/json" };
}

export async function fetchSalesReport(
  country: string,
  startDate: string,
  endDate: string,
): Promise<Record<string, unknown>[]> {
  const token = await getAccessToken();
  const marketplace = marketplaceId(country);
  const sellerId = Deno.env.get("SELLER_ID") ?? "";

  const createRes = await fetch(`${SP_API_BASE}/reports/2021-06-30/reports`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      reportType: REPORT_TYPE,
      marketplaceIds: [marketplace],
      dataStartTime: `${startDate}T00:00:00Z`,
      dataEndTime: `${endDate}T23:59:59Z`,
      reportOptions: { dateGranularity: "DAY", asinGranularity: "CHILD" },
    }),
  });
  if (!createRes.ok) throw new Error(`createReport: ${await createRes.text()}`);
  const { reportId } = await createRes.json();

  let documentId: string | null = null;
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 15000));
    const statusRes = await fetch(`${SP_API_BASE}/reports/2021-06-30/reports/${reportId}`, {
      headers: authHeaders(token),
    });
    if (!statusRes.ok) continue;
    const status = await statusRes.json();
    if (status.processingStatus === "DONE") {
      documentId = status.reportDocumentId;
      break;
    }
    if (status.processingStatus === "FATAL" || status.processingStatus === "CANCELLED") {
      throw new Error(`Report failed: ${status.processingStatus}`);
    }
  }
  if (!documentId) throw new Error("Report polling timeout");

  const docRes = await fetch(`${SP_API_BASE}/reports/2021-06-30/documents/${documentId}`, {
    headers: authHeaders(token),
  });
  if (!docRes.ok) throw new Error(`document meta: ${await docRes.text()}`);
  const docMeta = await docRes.json();
  const downloadRes = await fetch(docMeta.url);
  if (!downloadRes.ok) throw new Error("document download failed");
  let content = await downloadRes.arrayBuffer();
  if (docMeta.compressionAlgorithm === "GZIP") {
    const ds = new DecompressionStream("gzip");
    const stream = new Response(content).body!.pipeThrough(ds);
    content = await new Response(stream).arrayBuffer();
  }
  const reportJson = JSON.parse(new TextDecoder().decode(content));
  const now = new Date().toISOString();
  const txId = `${reportId}_${documentId}`;

  const rows: Record<string, unknown>[] = [];
  for (const item of reportJson.salesAndTrafficByAsin ?? []) {
    const sales = item.salesByAsin ?? {};
    const traffic = item.trafficByAsin ?? {};
    const childAsin = item.childAsin ?? item.asin;
    if (!childAsin || !item.date) continue;
    rows.push({
      ob_marketplace_id: marketplace,
      ob_seller_id: sellerId,
      child_asin: childAsin,
      parent_asin: item.parentAsin ?? null,
      sku: item.sku ?? null,
      ordered_product_sales_amount: sales.orderedProductSales?.amount ?? null,
      ordered_product_sales_currency_code: sales.orderedProductSales?.currencyCode ?? null,
      total_order_items: sales.totalOrderItems ?? null,
      units_ordered: sales.unitsOrdered ?? null,
      sessions: traffic.sessions ?? null,
      page_views: traffic.pageViews ?? null,
      buy_box_percentage: traffic.buyBoxPercentage ?? null,
      unit_session_percentage: traffic.unitSessionPercentage ?? null,
      ob_date: item.date,
      ob_transaction_id: txId,
      ob_file_name: `${REPORT_TYPE}_${reportId}.json`,
      ob_processed_at: now,
      ob_modified_date: now,
    });
  }
  return rows;
}
