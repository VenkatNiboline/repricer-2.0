import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Layout } from "../components/Layout";
import { useSettings } from "../components/SettingsProvider";
import { useAuth } from "../components/AuthProvider";

export function SettingsPage() {
  const { settings, setSettings, dbSynced, dbError } = useSettings();
  const { authConfigured } = useAuth();
  const [marketplaces, setMarketplaces] = useState<{ code: string; currency: string }[]>([]);

  useEffect(() => {
    api.marketplaces().then(setMarketplaces).catch(() => setMarketplaces([]));
  }, []);

  return (
    <Layout
      title="Settings"
      subtitle="Configure marketplace, sync rules, and FBM discount."
    >
      {authConfigured && (
        <div
          className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
            dbError
              ? "border-red-200 bg-red-50 text-red-700"
              : dbSynced
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-line bg-surface-subtle text-ink-muted"
          }`}
        >
          {dbError
            ? `Settings: ${dbError}`
            : dbSynced
              ? "Settings synced with server."
              : "Loading settings…"}
        </div>
      )}
      <div className="max-w-2xl space-y-6">
        <section className="panel p-6">
          <h2 className="text-sm font-semibold text-ink">Marketplace</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">Country</label>
              <select
                className="input-field"
                value={settings.country}
                onChange={(e) => setSettings({ country: e.target.value })}
              >
                {marketplaces.map((mp) => (
                  <option key={mp.code} value={mp.code}>
                    {mp.code} ({mp.currency})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">SP-API region</label>
              <select
                className="input-field"
                value={settings.region}
                onChange={(e) => setSettings({ region: e.target.value })}
              >
                <option value="EU">EU</option>
                <option value="US">US</option>
                <option value="FE">FE</option>
              </select>
            </div>
          </div>
        </section>

        <section className="panel p-6">
          <h2 className="text-sm font-semibold text-ink">Sync rules</h2>
          <div className="mt-4 space-y-3">
            {[
              {
                key: "syncSiblings" as const,
                label: "Sync pack-size variations",
                hint: "Update larger unit packs proportionally.",
              },
              {
                key: "syncFbm" as const,
                label: "Sync FBM offers",
                hint: "Update matching *FBM SKU at a discount below FBA.",
              },
              {
                key: "doubleOnly" as const,
                label: "Double packs only",
                hint: "Only sync siblings with exactly 2× units.",
              },
              {
                key: "dryRun" as const,
                label: "Default to dry-run",
                hint: "Validate without pushing unless you choose live update.",
              },
            ].map((item) => (
              <label
                key={item.key}
                className="flex cursor-pointer items-start gap-3 rounded-xl border border-line px-4 py-3"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={settings[item.key]}
                  onChange={(e) => setSettings({ [item.key]: e.target.checked })}
                />
                <span>
                  <span className="block text-sm font-medium text-ink">{item.label}</span>
                  <span className="block text-xs text-ink-muted">{item.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <section className="panel p-6">
          <h2 className="text-sm font-semibold text-ink">FBM discount</h2>
          <p className="mt-1 text-sm text-ink-muted">FBM price = FBA price × (1 − discount)</p>
          <div className="mt-4">
            <input
              type="range"
              min={0}
              max={30}
              value={Math.round(settings.fbmDiscount * 100)}
              onChange={(e) => setSettings({ fbmDiscount: Number(e.target.value) / 100 })}
              className="w-full"
            />
            <div className="mt-2 text-2xl font-semibold text-ink">
              {Math.round(settings.fbmDiscount * 100)}% off FBA
            </div>
          </div>
        </section>
      </div>
    </Layout>
  );
}
