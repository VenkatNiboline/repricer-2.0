import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api, QcFinding } from "../api/client";
import { Badge } from "../components/Badge";
import { Layout } from "../components/Layout";

export function QcDashboardPage() {
  const [findings, setFindings] = useState<QcFinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setFindings(await api.getQcFindings(false));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load QC findings");
    } finally {
      setLoading(false);
    }
  }

  async function runQc() {
    setRunning(true);
    try {
      await api.runQc();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "QC run failed");
    } finally {
      setRunning(false);
    }
  }

  async function resolve(id: number) {
    await api.resolveQcFinding(id);
    await load();
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <Layout
      title="QC Dashboard"
      subtitle="Data quality, pricing, and reflection checks."
      actions={
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button className="btn-primary" onClick={runQc} disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Run QC
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="panel overflow-hidden shadow-panel">
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading findings…
          </div>
        ) : (
          <div className="divide-y divide-line">
            {findings.map((f) => (
              <div key={f.id} className="flex items-start justify-between gap-4 px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        f.severity === "critical"
                          ? "warning"
                          : f.severity === "warning"
                            ? "warning"
                            : "muted"
                      }
                    >
                      {f.severity}
                    </Badge>
                    <span className="text-xs text-ink-muted">{f.agent_name}</span>
                  </div>
                  <p className="mt-1 text-sm text-ink">{f.message}</p>
                  {f.sku && (
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {f.sku} {f.country ? `· ${f.country}` : ""}
                    </p>
                  )}
                </div>
                <button className="btn-secondary text-xs" onClick={() => resolve(f.id)}>
                  Resolve
                </button>
              </div>
            ))}
            {!findings.length && (
              <div className="px-6 py-12 text-center text-sm text-ink-muted">No open findings.</div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
