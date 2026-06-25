import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, ExternalLink, Loader2, RefreshCw } from "lucide-react";
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

  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function copySubmissionId(id: string) {
    await navigator.clipboard.writeText(id);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId(null), 2000);
  }

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory(settings.country);
      setRows(data);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [settings.country]);

  const hasPendingReflection = rows.some(
    (row) => row.reflection_status === "pending" && row.pushed && !row.dry_run
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!hasPendingReflection) return;
    async function pollReflections() {
      try {
        await api.verifyPendingReflections();
      } catch {
        /* cron or next interval will retry */
      }
      await load(true);
    }
    const timer = window.setInterval(pollReflections, 60_000);
    return () => window.clearInterval(timer);
  }, [hasPendingReflection, load]);

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
      subtitle="Audit log of every repricing action. Pending reflections are rechecked every minute."
      actions={
        <button className="btn-secondary" onClick={() => load()} disabled={loading}>
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
            <table className="w-full min-w-[1280px] text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">When</th>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Old</th>
                  <th className="px-6 py-3">New</th>
                  <th className="px-6 py-3">Reflection</th>
                  <th className="px-6 py-3">Verified</th>
                  <th className="px-6 py-3">Submission ID</th>
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
                    <td className="max-w-[220px] px-6 py-3.5">
                      {row.submission_id ? (
                        <div className="flex items-center gap-1.5">
                          <span
                            className="truncate font-mono text-xs text-ink-muted"
                            title={row.submission_id}
                          >
                            {row.submission_id}
                          </span>
                          <button
                            type="button"
                            className="shrink-0 rounded p-1 text-ink-muted hover:bg-surface-subtle hover:text-ink"
                            title="Copy submission ID"
                            onClick={() => copySubmissionId(row.submission_id!)}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                          <Link
                            to={`/submissions?id=${encodeURIComponent(row.submission_id)}&sku=${encodeURIComponent(row.sku)}`}
                            className="shrink-0 rounded p-1 text-ink-muted hover:bg-surface-subtle hover:text-ink"
                            title="Check submission JSON"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                          {copiedId === row.submission_id && (
                            <span className="text-[10px] text-emerald-600">Copied</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
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
                    <td colSpan={9} className="px-6 py-12 text-center text-ink-muted">
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
