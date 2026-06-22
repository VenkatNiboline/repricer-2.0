import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, PriceHistoryRow } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

export function HistoryPage() {
  const { settings } = useSettings();
  const [rows, setRows] = useState<PriceHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getHistory(settings.country);
        if (!cancelled) setRows(data);
      } catch (err) {
        if (!cancelled) {
          setRows([]);
          setError(err instanceof Error ? err.message : "Failed to load history");
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

  return (
    <Layout
      title="Price History"
      subtitle="Audit log of every repricing action stored in Supabase."
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
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">When</th>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Old</th>
                  <th className="px-6 py-3">New</th>
                  <th className="px-6 py-3">Status</th>
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
                    <td className="px-6 py-3.5">
                      {row.dry_run ? (
                        <Badge>Dry run</Badge>
                      ) : row.pushed ? (
                        <Badge variant="success">Pushed</Badge>
                      ) : (
                        <Badge variant="warning">Failed</Badge>
                      )}
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-ink-muted">
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
