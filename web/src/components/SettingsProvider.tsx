import React, { createContext, useContext, useEffect } from "react";
import type { AppSettingsInput, RepricerSettings } from "../api/client";
import { api, loadSettings, saveSettings } from "../api/client";
import { useAuth } from "./AuthProvider";
import { supabaseConfigured } from "../lib/supabase";

interface SettingsContextValue {
  settings: RepricerSettings;
  setSettings: (next: Partial<RepricerSettings>) => void;
  dbSynced: boolean;
  dbError: string | null;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

function fromAppSettings(db: AppSettingsInput): Partial<RepricerSettings> {
  return {
    country: db.default_country,
    region: db.default_region,
    fbmDiscount: db.default_fbm_discount,
    syncSiblings: db.sync_siblings,
    syncFbm: db.sync_fbm,
  };
}

function toAppSettings(settings: RepricerSettings): AppSettingsInput {
  return {
    default_country: settings.country,
    default_region: settings.region,
    default_fbm_discount: settings.fbmDiscount,
    sync_siblings: settings.syncSiblings,
    sync_fbm: settings.syncFbm,
  };
}

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [settings, setSettingsState] = React.useState<RepricerSettings>(loadSettings);
  const [dbSynced, setDbSynced] = React.useState(false);
  const [dbError, setDbError] = React.useState<string | null>(null);

  useEffect(() => {
    if (!supabaseConfigured) return;
    let cancelled = false;
    api
      .getAppSettings()
      .then((db) => {
        if (cancelled) return;
        setSettingsState((prev) => {
          const merged = { ...prev, ...fromAppSettings(db) };
          saveSettings(merged);
          return merged;
        });
        setDbSynced(true);
        setDbError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setDbSynced(false);
          setDbError(err instanceof Error ? err.message : "Could not load app settings");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setSettings = (next: Partial<RepricerSettings>) => {
    setSettingsState((prev) => {
      const merged = { ...prev, ...next };
      saveSettings(merged);

      if (supabaseConfigured && user) {
        api
          .saveAppSettings(toAppSettings(merged))
          .then(() => {
            setDbSynced(true);
            setDbError(null);
          })
          .catch((err) => {
            setDbSynced(false);
            setDbError(err instanceof Error ? err.message : "Could not save app settings");
          });
      }

      return merged;
    });
  };

  return (
    <SettingsContext.Provider value={{ settings, setSettings, dbSynced, dbError }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
