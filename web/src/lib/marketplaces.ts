export interface Marketplace {
  code: string;
  label: string;
  currency: string;
  region: string;
}

/** EU Pan-European marketplaces supported by the repricer catalog sync. */
export const EU_MARKETPLACES: Marketplace[] = [
  { code: "DE", label: "Germany", currency: "EUR", region: "EU" },
  { code: "FR", label: "France", currency: "EUR", region: "EU" },
  { code: "IT", label: "Italy", currency: "EUR", region: "EU" },
  { code: "ES", label: "Spain", currency: "EUR", region: "EU" },
  { code: "NL", label: "Netherlands", currency: "EUR", region: "EU" },
  { code: "BE", label: "Belgium", currency: "EUR", region: "EU" },
  { code: "PL", label: "Poland", currency: "PLN", region: "EU" },
  { code: "SE", label: "Sweden", currency: "SEK", region: "EU" },
  { code: "UK", label: "United Kingdom", currency: "GBP", region: "EU" },
];

const MARKETPLACE_BY_CODE = Object.fromEntries(
  EU_MARKETPLACES.map((m) => [m.code, m])
) as Record<string, Marketplace>;

export function isSupportedMarketplace(country: string): boolean {
  return country.toUpperCase() in MARKETPLACE_BY_CODE;
}

export function marketplaceForCountry(country: string): Marketplace {
  const mp = MARKETPLACE_BY_CODE[country.toUpperCase()];
  if (!mp) throw new Error(`Unsupported marketplace: ${country}`);
  return mp;
}

/** Supabase table name for a marketplace catalog (e.g. sku_catalog_de). */
export function catalogTableForCountry(country: string): string {
  marketplaceForCountry(country);
  return `sku_catalog_${country.toLowerCase()}`;
}
