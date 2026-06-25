import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Search, TriangleAlert } from "lucide-react";
import { api, PriceUpdateResponse, VariationPreview } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

export function RepricePage() {
  const { settings } = useSettings();
  const [sku, setSku] = useState("");
  const [price, setPrice] = useState("");
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [currentCurrency, setCurrentCurrency] = useState("EUR");
  const [skuLookupLoading, setSkuLookupLoading] = useState(false);
  const [skuLookupError, setSkuLookupError] = useState<string | null>(null);
  const [preview, setPreview] = useState<VariationPreview | null>(null);
  const [result, setResult] = useState<PriceUpdateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmed = sku.trim();
    if (!trimmed) {
      setCurrentPrice(null);
      setSkuLookupError(null);
      setSkuLookupLoading(false);
      return;
    }

    setSkuLookupLoading(true);
    setSkuLookupError(null);

    const timer = window.setTimeout(() => {
      api
        .getSku(trimmed, settings.country)
        .then((data) => {
          setCurrentPrice(data.price);
          setCurrentCurrency(data.currency);
          setSkuLookupError(data.price == null ? "SKU found, but no price in catalog." : null);
        })
        .catch(() => {
          setCurrentPrice(null);
          setSkuLookupError("SKU not found in catalog.");
        })
        .finally(() => setSkuLookupLoading(false));
    }, 350);

    return () => window.clearTimeout(timer);
  }, [sku, settings.country]);

  async function handlePreview(e?: FormEvent) {
    e?.preventDefault();
    setError(null);
    setResult(null);
    const numericPrice = parseFloat(price);
    if (!sku.trim() || Number.isNaN(numericPrice) || numericPrice <= 0) {
      setError("Enter a valid SKU and price.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.preview(sku.trim(), numericPrice, settings);
      setPreview(data);
    } catch (err) {
      setPreview(null);
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdate(dryRun: boolean) {
    setError(null);
    const numericPrice = parseFloat(price);
    if (!sku.trim() || Number.isNaN(numericPrice)) return;
    setLoading(true);
    try {
      const data = await api.updatePrice(sku.trim(), numericPrice, settings, dryRun);
      setResult(data);
      if (!dryRun) {
        const primary = data.results.find((row) => row.link_kind === "primary");
        if (primary?.verified_price != null) {
          setCurrentPrice(primary.verified_price);
        } else if (primary?.pushed) {
          setCurrentPrice(primary.target_price);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout
      title="Reprice"
      subtitle="Update FBA price and sync linked variation packs and FBM offers."
    >
      <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
        <form onSubmit={handlePreview} className="panel p-6">
          <div className="text-sm font-medium text-ink">Price update</div>
          <p className="mt-1 text-sm text-ink-muted">
            Marketplace: <span className="font-medium text-ink">{settings.country}</span>
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">
                SKU (FBA)
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                <input
                  className="input-field pl-9"
                  placeholder="e.g. 7770531"
                  value={sku}
                  onChange={(e) => {
                    setSku(e.target.value);
                    setPreview(null);
                    setResult(null);
                  }}
                />
              </div>
              {sku.trim() && (
                <p className="mt-1.5 text-xs text-ink-muted">
                  {skuLookupLoading ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Looking up current price…
                    </span>
                  ) : skuLookupError ? (
                    <span className="text-amber-700">{skuLookupError}</span>
                  ) : (
                    <>
                      Current price{" "}
                      <span className="text-ink-faint">(live Amazon)</span>:{" "}
                      <span className="font-medium text-ink">
                        {formatPrice(currentPrice, currentCurrency)}
                      </span>
                    </>
                  )}
                </p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">
                Target FBA price
              </label>
              <input
                className="input-field"
                type="number"
                step="0.01"
                min="0"
                placeholder="32.99"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-2">
            <button type="submit" className="btn-secondary w-full" disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Preview changes
            </button>
            <button
              type="button"
              className="btn-secondary w-full"
              disabled={loading || !preview}
              onClick={() => handleUpdate(true)}
            >
              Dry-run validate
            </button>
            <button
              type="button"
              className="btn-primary w-full"
              disabled={loading || !preview}
              onClick={() => handleUpdate(false)}
            >
              Push live to Amazon
            </button>
          </div>

          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-700">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="break-all">{error}</span>
            </div>
          )}
        </form>

        <div className="space-y-6">
          {preview ? (
            <>
              <div className="panel p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-sm font-semibold text-ink">Preview</h2>
                  {preview.parent_sku && (
                    <Badge variant="muted">Parent: {preview.parent_sku}</Badge>
                  )}
                  {preview.fbm_pair && <Badge>FBM: {preview.fbm_pair}</Badge>}
                </div>

                <div className="mt-4 overflow-hidden rounded-xl border border-line">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-surface-subtle text-xs text-ink-muted">
                      <tr>
                        <th className="px-4 py-3 font-medium">SKU</th>
                        <th className="px-4 py-3 font-medium">Type</th>
                        <th className="px-4 py-3 font-medium">Current</th>
                        <th className="px-4 py-3 font-medium">Target</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-line">
                        <td className="px-4 py-3 font-medium">{preview.sku}</td>
                        <td className="px-4 py-3">
                          <Badge>FBA primary</Badge>
                        </td>
                        <td className="px-4 py-3 text-ink-muted">
                          {formatPrice(
                            preview.members.find((m) => m.is_source)?.current_price ?? null,
                            preview.currency
                          )}
                        </td>
                        <td className="px-4 py-3 font-medium">
                          {formatPrice(parseFloat(price), preview.currency)}
                        </td>
                      </tr>
                      {preview.linked_updates.map((row) => (
                        <tr key={row.sku} className="border-t border-line">
                          <td className="px-4 py-3 font-medium">{row.sku}</td>
                          <td className="px-4 py-3">
                            <Badge variant={row.link_kind === "fbm" ? "warning" : "default"}>
                              {row.link_kind === "fbm"
                                ? `FBM ×${row.multiplier.toFixed(2)}`
                                : `Pack ×${row.multiplier}`}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-ink-muted">
                            {formatPrice(row.current_price, preview.currency)}
                          </td>
                          <td className="px-4 py-3 font-medium">
                            {formatPrice(row.target_price, preview.currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {preview.members.length > 1 && (
                <div className="panel p-6">
                  <h2 className="text-sm font-semibold text-ink">Variation family</h2>
                  <div className="mt-4 space-y-2">
                    {preview.members.map((member) => (
                      <div
                        key={member.sku}
                        className="flex items-center justify-between rounded-xl border border-line px-4 py-3 text-sm"
                      >
                        <div>
                          <div className="font-medium text-ink">
                            {member.sku}
                            {member.is_source && (
                              <span className="ml-2 text-xs text-ink-muted">source</span>
                            )}
                          </div>
                          <div className="text-xs text-ink-muted">
                            {member.units} units
                            {member.size_label ? ` · ${member.size_label}` : ""}
                          </div>
                        </div>
                        <div className="font-medium">
                          {formatPrice(member.current_price, preview.currency)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="panel flex min-h-[320px] items-center justify-center p-6 text-sm text-ink-muted">
              Enter a SKU and price, then preview linked updates.
            </div>
          )}

          {result && (
            <div className="panel p-6">
              <h2 className="text-sm font-semibold text-ink">Results</h2>
              {result.history_saved === false && result.results.some((row) => row.pushed) && (
                <div className="mt-3 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Price change was not saved to history
                    {result.history_error ? `: ${result.history_error}` : "."}
                  </span>
                </div>
              )}
              <div className="mt-4 space-y-2">
                {result.results.map((row) => (
                  <div
                    key={row.sku}
                    className="flex items-start justify-between gap-4 rounded-xl border border-line px-4 py-3 text-sm"
                  >
                    <div>
                      <div className="flex items-center gap-2 font-medium text-ink">
                        {row.validation_ok ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <TriangleAlert className="h-4 w-4 text-red-500" />
                        )}
                        {row.sku}
                        <Badge variant="muted">{row.link_kind}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-ink-muted">
                        {row.status || (row.pushed ? "Pushed" : "Validated")}
                        {row.submission_id ? ` · ${row.submission_id}` : ""}
                      </div>
                      {row.error && (
                        <div className="mt-1 text-xs text-red-600">{row.error}</div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-medium">
                        {formatPrice(row.target_price, result.currency)}
                      </div>
                      {row.verified_price != null && (
                        <div className="text-xs text-emerald-600">
                          Verified {formatPrice(row.verified_price, result.currency)}
                        </div>
                      )}
                      {row.pushed && row.verified_price == null && row.error?.includes("expected") && (
                        <div className="text-xs text-amber-600">Reflection pending</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
