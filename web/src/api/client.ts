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
  product_name: string | null;
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
  history_saved?: boolean;
  history_error?: string | null;
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

export type ReflectionStatus =
  | "pending"
  | "reflected"
  | "mismatch"
  | "timeout"
  | "not_applicable";

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
  reflection_status?: ReflectionStatus;
  reflection_checked_at?: string | null;
  reflection_attempts?: number;
  created_at: string;
}

export interface SubmissionLookupResponse {
  submission_id: string;
  sku: string;
  country: string;
  currency: string;
  history?: PriceHistoryRow | null;
  current_price: number | null;
  listing: Record<string, unknown>;
  note: string;
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

export interface AuthUser {
  id: string;
  email?: string | null;
  role: string;
}

export interface HealthStatus {
  status: string;
  auth_configured: boolean;
  history_write_ready: boolean;
  db_configured: boolean;
  db_write_ready?: boolean;
}

export interface QcFinding {
  id: number;
  agent_name: string;
  check_id: string;
  severity: "critical" | "warning" | "info";
  sku?: string | null;
  country?: string | null;
  message: string;
  resolved: boolean;
  created_at: string;
}

export interface OverviewData {
  country: string;
  catalog_total: number;
  catalog_fba: number;
  catalog_fbm: number;
  catalog_synced_at: string | null;
  sales_revenue_7d: number;
  sales_units_7d: number;
  open_qc_critical: number;
  open_qc_warning: number;
  open_qc_total: number;
}

export interface SalesDailyRow {
  child_asin: string;
  sku?: string | null;
  ob_date: string;
  ordered_product_sales_amount?: number | null;
  units_ordered?: number | null;
  sessions?: number | null;
  buy_box_percentage?: number | null;
  unit_session_percentage?: number | null;
}

export interface SalesSummary {
  country: string;
  total_revenue_7d: number;
  total_units_7d: number;
  row_count: number;
}

const SETTINGS_KEY = "repricer-settings";
const CSRF_COOKIE = "repricer_csrf";

function getCsrfToken(): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

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
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init?.method ?? "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = getCsrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  authStatus: () => request<{ configured: boolean }>("/api/auth/status"),
  me: () => request<AuthUser | null>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<AuthUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  signup: (email: string, password: string) =>
    request<AuthUser | { message: string }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ ok: boolean }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    }),
  csrf: () => request<{ csrf_token: string }>("/api/auth/csrf"),
  overview: (country: string) => request<OverviewData>(`/api/overview?country=${country}`),
  marketplaces: () => request<Marketplace[]>("/api/marketplaces"),
  getSku: (sku: string, country: string, live = true) =>
    request<SkuSummary>(
      `/api/skus/${encodeURIComponent(sku)}?country=${country}&live=${live}`
    ),
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
  verifyHistory: (historyId: number) =>
    request<Record<string, unknown>>(`/api/history/${historyId}/verify`, { method: "POST" }),
  verifyPendingReflections: () =>
    request<{ checked: number; reflected: number; results: unknown[] }>(
      "/api/history/verify-pending",
      { method: "POST" }
    ),
  lookupSubmission: (
    submissionId: string,
    country: string,
    region = "EU",
    sku?: string
  ) => {
    const params = new URLSearchParams({
      submission_id: submissionId,
      country,
      region,
    });
    if (sku) params.set("sku", sku);
    return request<SubmissionLookupResponse>(`/api/submissions/lookup?${params}`);
  },
  getAppSettings: () => request<AppSettings>("/api/app-settings"),
  saveAppSettings: (settings: AppSettingsInput) =>
    request<AppSettings>("/api/app-settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  getQcFindings: (resolved = false) =>
    request<QcFinding[]>(`/api/qc/findings?resolved=${resolved}`),
  resolveQcFinding: (id: number) =>
    request<{ ok: boolean }>(`/api/qc/findings/${id}`, { method: "PATCH" }),
  runQc: () => request<unknown>("/api/qc/run", { method: "POST", body: "{}" }),
  getSalesSummary: (country: string) =>
    request<SalesSummary>(`/api/sales/summary?country=${country}`),
  syncSales: (country: string, region = "EU", days = 7) =>
    request<{ ok: boolean; rows: number }>("/api/sales/sync", {
      method: "POST",
      body: JSON.stringify({ country, region, days }),
    }),
  getSalesForSku: (country: string, sku: string, days = 30) =>
    request<SalesDailyRow[]>(
      `/api/sales?country=${country}&sku=${encodeURIComponent(sku)}&days=${days}`
    ),
};
