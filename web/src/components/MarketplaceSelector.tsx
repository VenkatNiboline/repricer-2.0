import { Globe } from "lucide-react";
import { EU_MARKETPLACES } from "../lib/marketplaces";
import { useSettings } from "./SettingsProvider";

export function MarketplaceSelector() {
  const { settings, setSettings } = useSettings();
  const current = EU_MARKETPLACES.find((m) => m.code === settings.country) ?? EU_MARKETPLACES[0];

  return (
    <div className="flex items-center gap-2">
      <Globe className="h-4 w-4 text-ink-muted" />
      <label className="sr-only" htmlFor="marketplace-select">
        Marketplace
      </label>
      <select
        id="marketplace-select"
        className="input-field min-w-[180px] py-1.5 text-sm"
        value={settings.country}
        onChange={(e) => {
          const mp = EU_MARKETPLACES.find((m) => m.code === e.target.value);
          if (mp) {
            setSettings({ country: mp.code, region: mp.region });
          }
        }}
      >
        {EU_MARKETPLACES.map((mp) => (
          <option key={mp.code} value={mp.code}>
            {mp.code} · {mp.label} ({mp.currency})
          </option>
        ))}
      </select>
      <span className="hidden text-xs text-ink-muted sm:inline">{current.label}</span>
    </div>
  );
}
