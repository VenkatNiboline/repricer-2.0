import { Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AuthProvider, useAuth } from "./components/AuthProvider";
import { SettingsProvider } from "./components/SettingsProvider";
import { FbmCatalogPage } from "./pages/FbmCatalogPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { QcDashboardPage } from "./pages/QcDashboardPage";
import { RepricePage } from "./pages/RepricePage";
import { RulesPage } from "./pages/RulesPage";
import { SalesDetailPage } from "./pages/SalesDetailPage";
import { SalesPerformancePage } from "./pages/SalesPerformancePage";
import { SettingsPage } from "./pages/SettingsPage";
import { SkuCatalogPage } from "./pages/SkuCatalogPage";
import { SubmissionCheckPage } from "./pages/SubmissionCheckPage";

function ProtectedApp() {
  const { user, loading, authConfigured } = useAuth();

  if (authConfigured) {
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
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/submissions" element={<SubmissionCheckPage />} />
        <Route path="/fbm" element={<FbmCatalogPage />} />
        <Route path="/sales" element={<SalesPerformancePage />} />
        <Route path="/sales/:sku" element={<SalesDetailPage />} />
        <Route path="/qc" element={<QcDashboardPage />} />
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
