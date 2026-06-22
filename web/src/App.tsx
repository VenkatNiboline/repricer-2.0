import { Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AuthProvider, useAuth } from "./components/AuthProvider";
import { SettingsProvider } from "./components/SettingsProvider";
import { supabaseConfigured } from "./lib/supabase";
import { FbmCatalogPage } from "./pages/FbmCatalogPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { RepricePage } from "./pages/RepricePage";
import { RulesPage } from "./pages/RulesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SkuCatalogPage } from "./pages/SkuCatalogPage";

function ProtectedApp() {
  const { user, loading } = useAuth();

  if (supabaseConfigured) {
    if (loading) {
      return (
        <div className="flex min-h-screen items-center justify-center text-sm text-ink-muted">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading session…
        </div>
      );
    }
    if (!user) return <LoginPage />;
  }

  return (
    <SettingsProvider>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/catalog" element={<SkuCatalogPage />} />
        <Route path="/reprice" element={<RepricePage />} />
        <Route path="/fbm" element={<FbmCatalogPage />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SettingsProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ProtectedApp />
    </AuthProvider>
  );
}
