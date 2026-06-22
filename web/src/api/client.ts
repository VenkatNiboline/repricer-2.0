export interface Marketplace {
  code: string;
  currency: string;
}

export interface SkuSummary {
  sku: string;
  fulfillment: string;
  price: number | null;
  currency: string;
  fba_pair: string | null;
  fbm_pair: string | null;
  parent_sku: string | null;
}

export interface VariationMember {
  sku: string;
  units: number;
  current_price: number | null;
  size_label: string;
  is_source: boolean;
}

export interface LinkedPrice {
  sku: string;
  units: number;
  current_price: number | null;
  target_price: number;
  multiplier: number;
  link_kind: string;
}

export interface VariationPreview {
  sku: string;
  country: string;
  currency: string;
  parent_sku: string | null;
  fbm_pair: string | null;
  members: VariationMember[];
  linked_updates: LinkedPrice[];
  fbm_target_price: number | null;
}

export interface CatalogStats {
  total: number;
  fba: number;
  fbm: number;
  fbm_suffix: number;
  synced_at: string | null;
  source: string;
}

export interface CatalogRow {
  sku: string;
  asin: string | null;
  product_type: string | null;
  fulfillment: string;
  price: number | null;
  currency: string;
  fba_pair: string;
  is_fbm: boolean;
}

export interface CatalogResponse {
  country: string;
  synced_at: string | null;
  source: string;
  count: number;
  stats: CatalogStats;
  rows: CatalogRow[];
}

export interface FbmSkuRow {
  sku: string;
  fba_pair: string;
  price: number | null;
  currency: string;
  detected_by: string;
}

export interface UpdateResult {
  sku: string;
  current_price: number | null;
  target_price: number;
  validation_ok: boolean;
  pushed: boolean;
  submission_id?: string | null;
  status?: string | null;
  verified_price?: number | null;
  error?: string | null;
  link_kind: string;
}

export interface PriceUpdateResponse {
  country: string;
  currency: string;
  parent_sku: string | null;
  results: UpdateResult[];
}

export interface RepricerSettings {
  country: string;
  region: string;
  syncSiblings: boolean;
  syncFbm: boolean;
  doubleOnly: boolean;
  fbmDiscount: number;
  dryRun: boolean;
}

export interface SkuRule {
  id?: number;
  sku: string;
  country: string;
  min_price?: number | null;
  max_price?: number | null;
  fbm_discount?: number | null;
  sync_siblings?: boolean | null;
  sync_fbm?: boolean | null;
  notes?: string | null;
  updated_at?: string | null;
}

export type SkuRuleInput = Omit<SkuRule, "id" | "updated_at">;

export interface PriceHistoryRow {
  id: number;
  sku: string;
  country: string;
  old_price: number | null;
  new_price: number;
  currency: string;
  link_kind: string;
  parent_sku?: string | null;
  dry_run: boolean;
  validation_ok?: boolean | null;
  pushed: boolean;
  submission_id?: string | null;
  verified_price?: number | null;
  error?: string | null;
  created_at: string;
}

export interface AppSettings {
  default_country: string;
  default_region: string;
  default_fbm_discount: number;
  sync_siblings: boolean;
  sync_fbm: boolean;
  updated_at?: string | null;
}

export type AppSettingsInput = Omit<AppSettings, "updated_at">;

import { getAccessToken } from "../lib/supabase";

const SETTINGS_KEY = "repricer-settings";

export function loadSettings(): RepricerSettings {
  const defaults: RepricerSettings = {
    country: "DE",
    region: "EU",
    syncSiblings: true,
    syncFbm: true,
    doubleOnly: false,
    fbmDiscount: 0.1,
    dryRun: true,
  };
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? { ...defaults, ...JSON.parse(raw) } : defaults;
  } catch {
    return defaults;
  }
}

export function saveSettings(settings: RepricerSettings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  marketplaces: () => request<Marketplace[]>("/api/marketplaces"),
  getSku: (sku: string, country: string) =>
    request<SkuSummary>(`/api/skus/${encodeURIComponent(sku)}?country=${country}`),
  preview: (sku: string, price: number, settings: RepricerSettings) => {
    const params = new URLSearchParams({
      price: String(price),
      country: settings.country,
      region: settings.region,
      double_only: String(settings.doubleOnly),
      sync_siblings: String(settings.syncSiblings),
      sync_fbm: String(settings.syncFbm),
      fbm_discount: String(settings.fbmDiscount),
    });
    return request<VariationPreview>(
      `/api/skus/${encodeURIComponent(sku)}/preview?${params}`
    );
  },
  catalogStats: (country: string, region = "EU", refresh = false) =>
    request<CatalogStats>(
      `/api/catalog/stats?country=${country}&region=${region}&refresh=${refresh}`
    ),
  catalog: (country: string, region = "EU", refresh = false, fulfillment?: string) => {
    const params = new URLSearchParams({
      country,
      region,
      refresh: String(refresh),
    });
    if (fulfillment) params.set("fulfillment", fulfillment);
    return request<CatalogResponse>(`/api/catalog?${params}`);
  },
  syncCatalog: (country: string, region = "EU") =>
    request<CatalogResponse>(`/api/catalog/sync?country=${country}&region=${region}`, {
      method: "POST",
    }),
  listFbmSkus: (country: string, suffixOnly = true) =>
    request<FbmSkuRow[]>(
      `/api/fbm-skus?country=${country}&suffix_only=${suffixOnly}`
    ),
  updatePrice: (
    sku: string,
    price: number,
    settings: RepricerSettings,
    dryRun?: boolean
  ) =>
    request<PriceUpdateResponse>("/api/repricer/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sku,
        price,
        country: settings.country,
        region: settings.region,
        dry_run: dryRun ?? settings.dryRun,
        verify: true,
        sync_siblings: settings.syncSiblings,
        sync_fbm: settings.syncFbm,
        double_only: settings.doubleOnly,
        fbm_discount: settings.fbmDiscount,
      }),
    }),
  getRules: (country?: string) =>
    request<SkuRule[]>(`/api/rules${country ? `?country=${country}` : ""}`),
  saveRule: (rule: SkuRuleInput) =>
    request<SkuRule>("/api/rules", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rule),
    }),
  deleteRule: (sku: string, country: string) =>
    request<{ ok: boolean }>(`/api/rules/${encodeURIComponent(sku)}?country=${country}`, {
      method: "DELETE",
    }),
  getHistory: (country?: string, sku?: string) => {
    const params = new URLSearchParams();
    if (country) params.set("country", country);
    if (sku) params.set("sku", sku);
    const q = params.toString();
    return request<PriceHistoryRow[]>(`/api/history${q ? `?${q}` : ""}`);
  },
  getAppSettings: () => request<AppSettings>("/api/app-settings"),
  saveAppSettings: (settings: AppSettingsInput) =>
    request<AppSettings>("/api/app-settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    }),
};
