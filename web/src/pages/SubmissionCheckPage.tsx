import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Copy, ExternalLink, Loader2, Search } from "lucide-react";
import { api, SubmissionLookupResponse } from "../api/client";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { formatPrice } from "../lib/utils";

export function SubmissionCheckPage() {
  const { settings } = useSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [submissionId, setSubmissionId] = useState(searchParams.get("id") ?? "");
  const [sku, setSku] = useState(searchParams.get("sku") ?? "");
  const [result, setResult] = useState<SubmissionLookupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const id = searchParams.get("id");
    if (id) setSubmissionId(id);
    const skuParam = searchParams.get("sku");
    if (skuParam) setSku(skuParam);
  }, [searchParams]);

  async function handleLookup(e?: FormEvent) {
    e?.preventDefault();
    const id = submissionId.trim();
    if (!id) {
      setError("Enter a submission ID.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false);
    try {
      const data = await api.lookupSubmission(id, settings.country, settings.region, sku.trim() || undefined);
      setResult(data);
      setSearchParams({
        id,
        ...(sku.trim() ? { sku: sku.trim() } : {}),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lookup failed");
    } finally {
      setLoading(false);
    }
  }

  async function copyJson() {
    if (!result) return;
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Layout
      title="Submission Check"
      subtitle="Look up the live Amazon Listings JSON for a price submission ID."
    >
      <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
        <form onSubmit={handleLookup} className="panel p-6">
          <div className="text-sm font-medium text-ink">Submission lookup</div>
          <p className="mt-1 text-sm text-ink-muted">
            Marketplace: <span className="font-medium text-ink">{settings.country}</span>
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">
                Submission ID
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                <input
                  className="input-field pl-9 font-mono text-xs"
                  placeholder="amzn1.sellerapps.listing..."
                  value={submissionId}
                  onChange={(e) => setSubmissionId(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">
                SKU <span className="text-ink-faint">(optional if in History)</span>
              </label>
              <input
                className="input-field font-mono text-xs"
                placeholder="e.g. 7700300"
                value={sku}
                onChange={(e) => setSku(e.target.value)}
              />
            </div>
          </div>

          <button type="submit" className="btn-primary mt-6 w-full" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Fetch JSON
          </button>

          {error && (
            <div className="mt-4 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-700">{error}</div>
          )}

          <p className="mt-4 text-xs text-ink-muted">
            Amazon does not expose an API to query by submission ID alone. We match your History
            record, then return the current listing JSON (price, issues, offers).
          </p>
        </form>

        <div className="panel flex min-h-[420px] flex-col overflow-hidden">
          {!result ? (
            <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">
              Paste a submission ID from History and click Fetch JSON.
            </div>
          ) : (
            <>
              <div className="border-b border-line px-6 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-ink">{result.sku}</div>
                    <div className="mt-1 font-mono text-xs text-ink-muted break-all">
                      {result.submission_id}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" className="btn-secondary" onClick={copyJson}>
                      <Copy className="h-4 w-4" />
                      {copied ? "Copied" : "Copy JSON"}
                    </button>
                    <a
                      className="btn-secondary"
                      href={`/history`}
                      title="Open History"
                    >
                      <ExternalLink className="h-4 w-4" />
                      History
                    </a>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-sm">
                  <span>
                    Live price:{" "}
                    <span className="font-medium text-ink">
                      {formatPrice(result.current_price, result.currency)}
                    </span>
                  </span>
                  {result.history?.new_price != null && (
                    <span className="text-ink-muted">
                      Target was {formatPrice(result.history.new_price, result.currency)}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs text-ink-muted">{result.note}</p>
              </div>
              <pre className="flex-1 overflow-auto bg-surface-subtle p-6 text-xs leading-relaxed text-ink">
                {JSON.stringify(result, null, 2)}
              </pre>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
