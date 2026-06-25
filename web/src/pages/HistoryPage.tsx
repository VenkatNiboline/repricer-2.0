import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import type { PriceHistoryRow } from "../api/client";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

function reflectionBadge(row: PriceHistoryRow) {
  const status = row.reflection_status ?? "not_applicable";
  if (row.dry_run) return <Badge>Dry run</Badge>;
  if (!row.pushed) return <Badge variant="warning">Failed</Badge>;
  switch (status) {
    case "reflected":
      return <Badge variant="success">Reflected</Badge>;
    case "pending":
      return <Badge variant="warning">Pending</Badge>;
    case "mismatch":
      return <Badge variant="warning">Mismatch</Badge>;
    case "timeout":
      return <Badge variant="warning">Timeout</Badge>;
    default:
      return <Badge variant="success">Pushed</Badge>;
  }
}

export function HistoryPage() {
  const { settings } = useSettings();
  const [rows, setRows] = useState<PriceHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory(settings.country);
      setRows(data);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [settings.country]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible") load();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  async function recheck(row: PriceHistoryRow) {
    try {
      await api.verifyHistory(row.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verify failed");
    }
  }

  return (
    <Layout
      title="Price History"
      subtitle="Audit log of every repricing action."
      actions={
        <button className="btn-secondary" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </button>
      }
    >
      <div className="panel overflow-hidden shadow-panel">
        {error && (
          <div className="border-b border-line bg-red-50 px-6 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading history…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">When</th>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Old</th>
                  <th className="px-6 py-3">New</th>
                  <th className="px-6 py-3">Reflection</th>
                  <th className="px-6 py-3">Verified</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-line">
                    <td className="px-6 py-3.5 text-ink-muted">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3.5 font-medium text-ink">{row.sku}</td>
                    <td className="px-6 py-3.5">
                      <Badge variant="muted">{row.link_kind}</Badge>
                    </td>
                    <td className="px-6 py-3.5">{formatPrice(row.old_price, row.currency)}</td>
                    <td className="px-6 py-3.5 font-medium">
                      {formatPrice(row.new_price, row.currency)}
                    </td>
                    <td className="px-6 py-3.5">{reflectionBadge(row)}</td>
                    <td className="px-6 py-3.5 text-ink-muted">
                      {row.verified_price != null
                        ? formatPrice(row.verified_price, row.currency)
                        : "—"}
                    </td>
                    <td className="px-6 py-3.5">
                      {row.reflection_status === "pending" && (
                        <button className="text-xs text-ink-muted hover:text-ink" onClick={() => recheck(row)}>
                          Re-check
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-ink-muted">
                      No price changes recorded yet.
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
