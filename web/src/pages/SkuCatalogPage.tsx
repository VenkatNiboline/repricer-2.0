import { useEffect, useState } from "react";
import { Download, Loader2, RefreshCw, Search } from "lucide-react";
import { api, CatalogRow } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

export function SkuCatalogPage() {
  const { settings } = useSettings();
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"ALL" | "FBA" | "FBM">("ALL");
  const [source, setSource] = useState<string>("");
  const [syncedAt, setSyncedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(refresh = false) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.catalog(
        settings.country,
        settings.region,
        refresh,
        filter === "ALL" ? undefined : filter
      );
      setRows(data.rows);
      setSource(data.source);
      setSyncedAt(data.synced_at);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : "Failed to load catalog");
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const data = await api.syncCatalog(settings.country, settings.region);
      setRows(
        filter === "ALL"
          ? data.rows
          : data.rows.filter((row) => row.fulfillment === filter)
      );
      setSource(data.source);
      setSyncedAt(data.synced_at);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load(false);
  }, [settings.country, settings.region, filter]);

  const filtered = rows.filter((row) =>
    row.sku.toLowerCase().includes(query.toLowerCase()) ||
    (row.asin || "").toLowerCase().includes(query.toLowerCase())
  );

  function exportCsv() {
    const header = "sku,asin,fulfillment,price,currency,product_type\n";
    const body = filtered
      .map((row) =>
        [row.sku, row.asin ?? "", row.fulfillment, row.price ?? "", row.currency, row.product_type ?? ""].join(",")
      )
      .join("\n");
    const blob = new Blob([header + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `catalog-${settings.country}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Layout
      title="SKU Catalog"
      subtitle="All SKUs loaded from Amazon SP-API and cached locally for fast access."
      actions={
        <>
          <button className="btn-secondary" onClick={handleSync} disabled={syncing}>
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync from Amazon
          </button>
          <button className="btn-secondary" onClick={exportCsv} disabled={!filtered.length}>
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </>
      }
    >
      <div className="panel overflow-hidden shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
          <div className="relative min-w-[240px] flex-1 max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input
              className="input-field pl-9"
              placeholder="Search SKU or ASIN…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            {(["ALL", "FBA", "FBM"] as const).map((value) => (
              <button
                key={value}
                className={filter === value ? "btn-primary" : "btn-secondary"}
                onClick={() => setFilter(value)}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <div className="border-b border-line px-6 py-2 text-xs text-ink-muted">
          {loading
            ? "Loading…"
            : `${filtered.length} SKUs · source: ${source}${syncedAt ? ` · ${new Date(syncedAt).toLocaleString()}` : ""}`}
        </div>

        {error && (
          <div className="border-b border-line bg-red-50 px-6 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            {source ? "Loading from cache…" : "First sync scans Amazon (~1 min)…"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">ASIN</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Fulfillment</th>
                  <th className="px-6 py-3">Price</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.sku} className="border-t border-line hover:bg-surface-muted/60">
                    <td className="px-6 py-3.5 font-medium text-ink">{row.sku}</td>
                    <td className="px-6 py-3.5 text-ink-muted">{row.asin || "—"}</td>
                    <td className="px-6 py-3.5 text-ink-muted">{row.product_type || "—"}</td>
                    <td className="px-6 py-3.5">
                      <Badge variant={row.fulfillment === "FBM" ? "warning" : "default"}>
                        {row.fulfillment}
                      </Badge>
                    </td>
                    <td className="px-6 py-3.5 font-medium">
                      {formatPrice(row.price, row.currency)}
                    </td>
                  </tr>
                ))}
                {!filtered.length && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-ink-muted">
                      No SKUs found. Click &quot;Sync from Amazon&quot; to load your catalog.
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
