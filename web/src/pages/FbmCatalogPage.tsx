import { useEffect, useState } from "react";
import { Download, Loader2, Search } from "lucide-react";
import type { FbmSkuRow } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { api } from "../api/client";
import { formatPrice } from "../lib/utils";

export function FbmCatalogPage() {
  const { settings } = useSettings();
  const [rows, setRows] = useState<FbmSkuRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listFbmSkus(settings.country);
        if (!cancelled) setRows(data);
      } catch (err) {
        if (!cancelled) {
          setRows([]);
          setError(err instanceof Error ? err.message : "Failed to load FBM SKUs");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [settings.country]);

  const filtered = rows.filter(
    (row) =>
      row.sku.toLowerCase().includes(query.toLowerCase()) ||
      row.fba_pair.toLowerCase().includes(query.toLowerCase())
  );

  function exportCsv() {
    const header = "sku,fba_pair,price,currency,detected_by\n";
    const body = filtered
      .map((row) =>
        [row.sku, row.fba_pair, row.price ?? "", row.currency, row.detected_by].join(",")
      )
      .join("\n");
    const blob = new Blob([header + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fbm-skus-${settings.country}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Layout
      title="FBM Catalog"
      subtitle={`FBM offers in ${settings.country} from sku_catalog_${settings.country.toLowerCase()}.`}
      actions={
        <button className="btn-secondary" onClick={exportCsv} disabled={!filtered.length}>
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      }
    >
      <div className="panel overflow-hidden shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
          <div className="relative min-w-[240px] flex-1 max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input
              className="input-field pl-9"
              placeholder="Search SKU or FBA pair…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="text-sm text-ink-muted">{filtered.length} FBM SKUs</div>
        </div>

        {error && (
          <div className="border-b border-line bg-red-50 px-6 py-3 text-sm text-red-700">{error}</div>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading from Supabase…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">FBM SKU</th>
                  <th className="px-6 py-3">FBA pair</th>
                  <th className="px-6 py-3">Price</th>
                  <th className="px-6 py-3">Detected</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.sku} className="border-t border-line">
                    <td className="px-6 py-3.5 font-medium text-ink">{row.sku}</td>
                    <td className="px-6 py-3.5 text-ink-muted">{row.fba_pair}</td>
                    <td className="px-6 py-3.5 font-medium">
                      {formatPrice(row.price, row.currency)}
                    </td>
                    <td className="px-6 py-3.5">
                      <Badge variant="muted">{row.detected_by}</Badge>
                    </td>
                  </tr>
                ))}
                {!filtered.length && (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-ink-muted">
                      No FBM SKUs in Supabase. Sync the catalog first.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}
