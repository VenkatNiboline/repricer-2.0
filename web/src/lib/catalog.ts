import { api, CatalogStats } from "../api/client";
import { EU_MARKETPLACES } from "./marketplaces";

export async function fetchCatalog(
  country: string,
  region = "EU",
  fulfillment?: string
): Promise<{ stats: CatalogStats; rows: import("../api/client").CatalogRow[] }> {
  const data = await api.catalog(country, region, false, fulfillment);
  return { stats: data.stats, rows: data.rows };
}

export async function invokeCatalogSync(country: string, region = "EU") {
  const data = await api.syncCatalog(country, region);
  return {
    ok: true,
    count: data.count,
    stats: data.stats,
  };
}

export async function invokeCatalogSyncAll(
  onProgress?: (country: string, index: number, total: number) => void
) {
  const results: { country: string; count: number; error?: string }[] = [];
  const total = EU_MARKETPLACES.length;

  for (let i = 0; i < EU_MARKETPLACES.length; i++) {
    const mp = EU_MARKETPLACES[i];
    onProgress?.(mp.code, i + 1, total);
    try {
      const result = await invokeCatalogSync(mp.code, mp.region);
      results.push({ country: mp.code, count: result.count ?? 0 });
    } catch (err) {
      results.push({
        country: mp.code,
        count: 0,
        error: err instanceof Error ? err.message : "Sync failed",
      });
    }
  }

  return results;
}

export async function checkApiHealth() {
  try {
    const health = await api.health();
    return health.db_configured;
  } catch {
    return false;
  }
}
