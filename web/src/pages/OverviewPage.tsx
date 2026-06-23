import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2, RefreshCw } from "lucide-react";
import type { OverviewData } from "../api/client";
import { api } from "../api/client";
import { checkApiHealth, invokeCatalogSync } from "../lib/catalog";
import { marketplaceForCountry } from "../lib/marketplaces";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { useSettings } from "../components/SettingsProvider";

export function OverviewPage() {
  const { settings } = useSettings();
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const marketplace = marketplaceForCountry(settings.country);

  async function loadStats() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.overview(settings.country);
      setOverview(data);
    } catch (err) {
      setOverview(null);
      setError(err instanceof Error ? err.message : "Failed to load overview");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    checkApiHealth().then(setConnected);
    loadStats();
  }, [settings.country]);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      await invokeCatalogSync(settings.country, settings.region);
      await loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Layout
      title="Overview"
      subtitle={`${marketplace.label} (${settings.country})`}
      actions={
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={handleSync} disabled={syncing}>
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync {settings.country}
          </button>
          <Link to="/reprice" className="btn-primary">
            Reprice SKU
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      }
    >
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-ink-muted">
        <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`} />
        {connected ? "API connected" : "API not reachable"}
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Total SKUs"
          value={loading ? "…" : String(overview?.catalog_total ?? "—")}
          hint={overview?.catalog_synced_at ? `synced ${new Date(overview.catalog_synced_at).toLocaleString()}` : marketplace.label}
        />
        <MetricCard label="Revenue (7d)" value={loading ? "…" : overview ? `€${overview.sales_revenue_7d.toFixed(2)}` : "—"} hint="Ordered product sales" />
        <MetricCard label="Units (7d)" value={loading ? "…" : String(overview?.sales_units_7d ?? "—")} hint="From sales ETL" />
        <MetricCard
          label="QC alerts"
          value={loading ? "…" : String(overview?.open_qc_total ?? 0)}
          hint={
            overview
              ? `${overview.open_qc_critical} critical · ${overview.open_qc_warning} warning`
              : "Open findings"
          }
        />
      </div>

      <div className="mt-6 flex gap-3">
        <Link to="/sales" className="btn-secondary text-sm">Sales performance</Link>
        <Link to="/qc" className="btn-secondary text-sm">QC dashboard</Link>
        <Link to="/history" className="btn-secondary text-sm">Price history</Link>
      </div>
    </Layout>
  );
}
