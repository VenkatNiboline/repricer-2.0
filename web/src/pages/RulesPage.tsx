import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import type { SkuRule, SkuRuleInput } from "../api/client";
import { api } from "../api/client";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";

const emptyRule = (country: string): SkuRuleInput => ({
  sku: "",
  country,
  min_price: null,
  max_price: null,
  fbm_discount: null,
  sync_siblings: null,
  sync_fbm: null,
  notes: "",
});

export function RulesPage() {
  const { settings } = useSettings();
  const [rules, setRules] = useState<SkuRule[]>([]);
  const [form, setForm] = useState<SkuRuleInput>(emptyRule(settings.country));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRules(settings.country);
      setRules(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setForm(emptyRule(settings.country));
    load();
  }, [settings.country]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.sku.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveRule({ ...form, sku: form.sku.trim(), country: settings.country });
      setForm(emptyRule(settings.country));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rule");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(sku: string) {
    try {
      await api.deleteRule(sku, settings.country);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete rule");
    }
  }

  return (
    <Layout
      title="SKU Rules"
      subtitle="Per-SKU min/max prices and FBM overrides stored in Supabase."
    >
      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <form onSubmit={onSubmit} className="panel p-6">
          <div className="text-sm font-semibold text-ink">Add / update rule</div>
          <div className="mt-4 space-y-3">
            <input
              className="input-field"
              placeholder="SKU"
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                className="input-field"
                type="number"
                step="0.01"
                placeholder="Min price"
                value={form.min_price ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    min_price: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
              <input
                className="input-field"
                type="number"
                step="0.01"
                placeholder="Max price"
                value={form.max_price ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_price: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
            <input
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              max="0.99"
              placeholder="FBM discount override (0.10)"
              value={form.fbm_discount ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  fbm_discount: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
            <textarea
              className="input-field min-h-[80px]"
              placeholder="Notes"
              value={form.notes ?? ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
          <button className="btn-primary mt-4 w-full" disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Save rule
          </button>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </form>

        <div className="panel overflow-hidden shadow-panel">
          {loading ? (
            <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-ink-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading rules…
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-medium text-ink-muted">
                <tr>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">Min</th>
                  <th className="px-6 py-3">Max</th>
                  <th className="px-6 py-3">FBM %</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={`${rule.sku}-${rule.country}`} className="border-t border-line">
                    <td className="px-6 py-3.5 font-medium">{rule.sku}</td>
                    <td className="px-6 py-3.5">{rule.min_price ?? "—"}</td>
                    <td className="px-6 py-3.5">{rule.max_price ?? "—"}</td>
                    <td className="px-6 py-3.5">
                      {rule.fbm_discount != null
                        ? `${Math.round(rule.fbm_discount * 100)}%`
                        : "—"}
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <button
                        className="btn-secondary px-2 py-1.5"
                        onClick={() => onDelete(rule.sku)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {!rules.length && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-ink-muted">
                      No rules yet for {settings.country}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  );
}
