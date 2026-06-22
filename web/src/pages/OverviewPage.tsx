import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2, RefreshCw } from "lucide-react";
import { api, CatalogStats } from "../api/client";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { useSettings } from "../components/SettingsProvider";

export function OverviewPage() {
  const { settings } = useSettings();
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [apiOk, setApiOk] = useState(false);

  async function loadStats(refresh = false) {
    setLoading(true);
    try {
      await api.health();
      setApiOk(true);
      const data = await api.catalogStats(settings.country, settings.region, refresh);
      setStats(data);
    } catch {
      setApiOk(false);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const data = await api.syncCatalog(settings.country, settings.region);
      setStats(data.stats);
      setApiOk(true);
    } catch {
      setApiOk(false);
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    loadStats(false);
  }, [settings.country, settings.region]);

  return (
    <Layout
      title="Overview"
      subtitle="Track FBA prices, variation sync, and FBM discounts across your catalog."
      actions={
        <div className="flex items-center gap-2">
          <button
            className="btn-secondary"
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Sync catalog
          </button>
          <Link to="/reprice" className="btn-primary">
            Reprice SKU
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      }
    >
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-ink-muted">
        <span
          className={`h-1.5 w-1.5 rounded-full ${apiOk ? "bg-emerald-500" : "bg-red-500"}`}
        />
        {apiOk ? "Connected to Amazon SP-API" : "API offline — start the backend"}
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Total SKUs"
          value={loading ? "…" : String(stats?.total ?? "—")}
          hint={stats?.synced_at ? `synced ${new Date(stats.synced_at).toLocaleString()}` : `in ${settings.country}`}
        />
        <MetricCard
          label="FBA SKUs"
          value={loading ? "…" : String(stats?.fba ?? "—")}
          hint="Amazon fulfilled"
        />
        <MetricCard
          label="FBM SKUs"
          value={loading ? "…" : String(stats?.fbm_suffix ?? "—")}
          hint="*FBM suffix offers"
        />
        <MetricCard
          label="FBM discount"
          value={`${Math.round(settings.fbmDiscount * 100)}%`}
          hint="below FBA price"
        />
      </div>

      {stats && (
        <p className="mt-3 text-xs text-ink-muted">
          Data source: <span className="font-medium text-ink">{stats.source}</span>
          {stats.source === "cache" && " — click Sync catalog to refresh from Amazon"}
        </p>
      )}

      <div className="mt-6 panel overflow-hidden shadow-panel">
        <div className="border-b border-line px-6 py-4">
          <h2 className="text-sm font-semibold text-ink">Quick start</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Set an FBA price and automatically update linked pack sizes and FBM offers.
          </p>
        </div>
        <div className="grid gap-px bg-line md:grid-cols-3">
          {[
            {
              step: "1",
              title: "Sync catalog",
              body: "Load all SKUs once from Amazon. Cached locally for fast UI.",
            },
            {
              step: "2",
              title: "Preview changes",
              body: "See calculated prices for double-unit packs and FBM at -10%.",
            },
            {
              step: "3",
              title: "Validate & push",
              body: "Dry-run first, then push live to Seller Central via SP-API.",
            },
          ].map((item) => (
            <div key={item.step} className="bg-white p-6">
              <div className="mb-3 flex h-7 w-7 items-center justify-center rounded-full bg-surface-subtle text-xs font-semibold text-ink">
                {item.step}
              </div>
              <div className="text-sm font-semibold text-ink">{item.title}</div>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{item.body}</p>
            </div>
          ))}
        </div>
      </div>

      {loading && (
        <div className="mt-6 flex items-center gap-2 text-sm text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading catalog stats…
        </div>
      )}
    </Layout>
  );
}
