import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { api, SalesDailyRow } from "../api/client";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

export function SalesDetailPage() {
  const { sku } = useParams<{ sku: string }>();
  const { settings } = useSettings();
  const [rows, setRows] = useState<SalesDailyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sku) return;
    setLoading(true);
    api
      .getSalesForSku(settings.country, sku, 30)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [sku, settings.country]);

  const totalRevenue = rows.reduce((s, r) => s + (r.ordered_product_sales_amount ?? 0), 0);
  const totalUnits = rows.reduce((s, r) => s + (r.units_ordered ?? 0), 0);

  return (
    <Layout
      title={`Sales: ${sku}`}
      subtitle={`${settings.country} — last 30 days`}
      actions={
        <Link to="/sales" className="btn-secondary">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
      }
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="mb-4 grid gap-4 md:grid-cols-3">
        <div className="panel p-4">
          <div className="text-xs text-ink-muted">Revenue (30d)</div>
          <div className="text-xl font-semibold">{formatPrice(totalRevenue, "EUR")}</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs text-ink-muted">Units (30d)</div>
          <div className="text-xl font-semibold">{totalUnits}</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs text-ink-muted">Data points</div>
          <div className="text-xl font-semibold">{rows.length}</div>
        </div>
      </div>

      <div className="panel overflow-hidden shadow-panel">
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-subtle text-xs text-ink-muted">
              <tr>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Revenue</th>
                <th className="px-6 py-3">Units</th>
                <th className="px-6 py-3">Sessions</th>
                <th className="px-6 py-3">Buy box %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ob_date} className="border-t border-line">
                  <td className="px-6 py-3">{row.ob_date}</td>
                  <td className="px-6 py-3">
                    {formatPrice(row.ordered_product_sales_amount ?? null, "EUR")}
                  </td>
                  <td className="px-6 py-3">{row.units_ordered ?? "—"}</td>
                  <td className="px-6 py-3">{row.sessions ?? "—"}</td>
                  <td className="px-6 py-3">
                    {row.buy_box_percentage != null ? `${row.buy_box_percentage.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-ink-muted">
                    No sales data for this SKU. Run a sales sync first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  );
}
