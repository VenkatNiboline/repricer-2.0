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
  US: "ATVPDKIKX0DER",
};

const COUNTRY_CURRENCIES: Record<string, string> = {
  DE: "EUR",
  FR: "EUR",
  IT: "EUR",
  ES: "EUR",
  NL: "EUR",
  BE: "EUR",
  PL: "PLN",
  SE: "SEK",
  UK: "GBP",
  US: "USD",
};

const SUPPORTED_COUNTRIES = new Set(Object.keys(MARKETPLACE_IDS).filter((c) => c !== "US"));

export function catalogTableForCountry(country: string): string {
  const code = country.toUpperCase();
  if (!SUPPORTED_COUNTRIES.has(code)) {
    throw new Error(`Unsupported marketplace: ${country}`);
  }
  return `sku_catalog_${code.toLowerCase()}`;
}

const SP_API_BASE: Record<string, string> = {
  EU: "https://sellingpartnerapi-eu.amazon.com",
  US: "https://sellingpartnerapi-na.amazon.com",
  FE: "https://sellingpartnerapi-fe.amazon.com",
};

const FBA_CHANNELS = new Set([
  "AMAZON_EU",
  "AMAZON_NA",
  "AMAZON_JP",
  "AMAZON_IN",
  "AMAZON_CN",
]);

export function marketplaceId(country: string): string {
  const code = country.toUpperCase();
  const id = MARKETPLACE_IDS[code];
  if (!id) throw new Error(`Unknown country: ${country}`);
  return id;
}

export function currencyForCountry(country: string): string {
  return COUNTRY_CURRENCIES[country.toUpperCase()] ?? "EUR";
}

export function isFbmSku(sku: string): boolean {
  return sku.toUpperCase().endsWith("FBM");
}

export function fbaSkuFor(sku: string): string {
  return isFbmSku(sku) ? sku.slice(0, -3) : sku;
}

function fulfillmentChannels(
  listing: Record<string, unknown>,
  marketplaceIdValue: string,
): string[] {
  const attrs = (listing.attributes ?? {}) as Record<string, unknown>;
  const entries = (attrs.fulfillment_availability ?? []) as Record<string, unknown>[];
  const codes: string[] = [];
  for (const entry of entries) {
    const mp = entry.marketplace_id as string | undefined;
    if (mp && mp !== marketplaceIdValue) continue;
    const code = entry.fulfillment_channel_code as string | undefined;
    if (code) codes.push(code);
  }
  return codes;
}

export function classifyFulfillment(
  sku: string,
  listing: Record<string, unknown>,
  marketplaceIdValue: string,
): string {
  if (isFbmSku(sku)) return "FBM";
  const codes = fulfillmentChannels(listing, marketplaceIdValue);
  if (codes.some((c) => FBA_CHANNELS.has(c) || c.startsWith("AMAZON"))) return "FBA";
  if (codes.includes("DEFAULT")) return "FBM";
  return "UNKNOWN";
}

function priceFromPurchasableOffer(
  offers: Record<string, unknown>[],
  marketplaceIdValue: string,
): number | null {
  for (const offer of offers) {
    if (offer.marketplace_id !== marketplaceIdValue) continue;
    const ourPrices = (offer.our_price ?? []) as Record<string, unknown>[];
    for (const ourPrice of ourPrices) {
      const schedules = (ourPrice.schedule ?? []) as Record<string, unknown>[];
      for (const schedule of schedules) {
        const value = schedule.value_with_tax;
        if (value != null) return Number(value);
      }
    }
  }
  return null;
}

function priceFromOffersSection(
  offers: Record<string, unknown>[],
  marketplaceIdValue: string,
): number | null {
  for (const offer of offers) {
    if (offer.marketplaceId !== marketplaceIdValue) continue;
    const price = (offer.price ?? {}) as Record<string, unknown>;
    const amount = price.amount;
    if (amount != null) return Number(amount);
  }
  return null;
}

export function extractCurrentPrice(
  listing: Record<string, unknown>,
  marketplaceIdValue: string,
): number | null {
  const attrs = (listing.attributes ?? {}) as Record<string, unknown>;
  const purchasable = (attrs.purchasable_offer ?? []) as Record<string, unknown>[];
  const fromPurchasable = priceFromPurchasableOffer(purchasable, marketplaceIdValue);
  if (fromPurchasable != null) return fromPurchasable;
  const offers = (listing.offers ?? []) as Record<string, unknown>[];
  return priceFromOffersSection(offers, marketplaceIdValue);
}

export function extractProductName(listing: Record<string, unknown>): string | null {
  const summaries = (listing.summaries ?? []) as Record<string, unknown>[];
  const fromSummary = summaries[0]?.itemName as string | undefined;
  if (fromSummary) return fromSummary;

  const attrs = (listing.attributes ?? {}) as Record<string, unknown>;
  const itemNames = (attrs.item_name ?? []) as Record<string, unknown>[];
  for (const entry of itemNames) {
    const value = entry.value as string | undefined;
    if (value) return value;
  }
  return null;
}

export async function getAccessToken(): Promise<string> {
  const refreshToken = Deno.env.get("LWA_REFRESH_TOKEN");
  const clientId = Deno.env.get("LWA_CLIENT_ID");
  const clientSecret = Deno.env.get("LWA_CLIENT_SECRET");
  if (!refreshToken || !clientId || !clientSecret) {
    throw new Error("Missing Amazon LWA credentials in Edge Function secrets");
  }

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: clientId,
    client_secret: clientSecret,
  });

  const response = await fetch("https://api.amazon.com/auth/o2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    throw new Error(`Amazon token error: HTTP ${response.status}`);
  }

  const data = await response.json();
  if (!data.access_token) throw new Error("Amazon token response missing access_token");
  return data.access_token as string;
}

export interface CatalogRow {
  sku: string;
  asin: string | null;
  product_name: string | null;
  product_type: string | null;
  fulfillment: string;
  price: number | null;
  currency: string;
  fba_pair: string;
  is_fbm: boolean;
}

export function rowFromItem(
  item: Record<string, unknown>,
  country: string,
): CatalogRow | null {
  const sku = (item.sku as string) ?? "";
  if (!sku) return null;

  const mpId = marketplaceId(country);
  const currency = currencyForCountry(country);
  const fulfillment = classifyFulfillment(sku, item, mpId);
  const price = extractCurrentPrice(item, mpId);
  const productName = extractProductName(item);
  const summaries = (item.summaries ?? []) as Record<string, unknown>[];
  const asin = summaries[0]?.asin as string | undefined;
  const productType = summaries[0]?.productType as string | undefined;

  return {
    sku,
    asin: asin ?? null,
    product_name: productName,
    product_type: productType ?? null,
    fulfillment,
    price,
    currency,
    fba_pair: isFbmSku(sku) ? fbaSkuFor(sku) : sku,
    is_fbm: isFbmSku(sku),
  };
}

export async function scanAmazonCatalog(
  country: string,
  region: string,
  sellerId: string,
  accessToken: string,
): Promise<CatalogRow[]> {
  const baseUrl = SP_API_BASE[region.toUpperCase()] ?? SP_API_BASE.EU;
  const mpId = marketplaceId(country);
  const rows: CatalogRow[] = [];
  let pageToken: string | undefined;

  while (true) {
    const params = new URLSearchParams({
      marketplaceIds: mpId,
      includedData: "summaries,attributes,offers",
      pageSize: "20",
    });
    if (pageToken) params.set("pageToken", pageToken);

    const url = `${baseUrl}/listings/2021-08-01/items/${sellerId}?${params}`;
    const response = await fetch(url, {
      headers: {
        "x-amz-access-token": accessToken,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Amazon listings search failed (${response.status}): ${text}`);
    }

    const payload = await response.json();
    const items = (payload.items ?? []) as Record<string, unknown>[];
    for (const item of items) {
      const row = rowFromItem(item, country);
      if (row) rows.push(row);
    }

    pageToken = (payload.pagination as Record<string, string> | undefined)?.nextToken;
    if (!pageToken) break;
  }

  rows.sort((a, b) => a.sku.localeCompare(b.sku));
  return rows;
}
