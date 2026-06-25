import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api, SalesSummary } from "../api/client";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { useSettings } from "../components/SettingsProvider";
import { marketplaceForCountry } from "../lib/marketplaces";

export function SalesPerformancePage() {
  const { settings } = useSettings();
  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const marketplace = marketplaceForCountry(settings.country);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setSummary(await api.getSalesSummary(settings.country));
    } catch (err) {
      setSummary(null);
      setError(err instanceof Error ? err.message : "Failed to load sales");
    } finally {
      setLoading(false);
    }
  }

  async function sync() {
    setSyncing(true);
    setError(null);
    try {
      await api.syncSales(settings.country, settings.region, 7);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sales sync failed");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load();
  }, [settings.country]);

  return (
    <Layout
      title="Sales Performance"
      subtitle={`${marketplace.label} — last 7 days from Amazon Sales & Traffic report.`}
      actions={
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button className="btn-primary" onClick={sync} disabled={syncing}>
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Sync sales (7d)
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Revenue (7d)"
          value={loading ? "…" : summary ? `€${summary.total_revenue_7d.toFixed(2)}` : "—"}
          hint={marketplace.currency}
        />
        <MetricCard
          label="Units (7d)"
          value={loading ? "…" : summary ? String(summary.total_units_7d) : "—"}
          hint="Ordered units"
        />
        <MetricCard
          label="Data rows"
          value={loading ? "…" : summary ? String(summary.row_count) : "—"}
          hint="Daily ASIN rows loaded"
        />
      </div>
    </Layout>
  );
}
