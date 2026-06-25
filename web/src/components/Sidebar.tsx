import { NavLink } from "react-router-dom";
import {
  BarChart3,
  History,
  LayoutDashboard,
  List,
  Package,
  Settings,
  Shield,
  ShieldCheck,
  Tag,
  Zap,
} from "lucide-react";
import { useAuth } from "./AuthProvider";
import { cn } from "../lib/utils";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/catalog", label: "SKU Catalog", icon: List },
  { to: "/reprice", label: "Reprice", icon: Zap },
  { to: "/sales", label: "Sales", icon: BarChart3 },
  { to: "/rules", label: "SKU Rules", icon: Shield },
  { to: "/history", label: "History", icon: History },
  { to: "/qc", label: "QC", icon: ShieldCheck },
  { to: "/fbm", label: "FBM Catalog", icon: Package },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const { user, signOut } = useAuth();
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-white">
      <div className="border-b border-line px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-semibold text-white">
            R
          </div>
          <div>
            <div className="text-sm font-semibold text-ink">Repricer</div>
            <div className="text-xs text-ink-muted">Amazon Pricing</div>
          </div>
        </div>
      </div>

      <div className="px-3 py-4">
        <div className="mb-2 px-2 text-[11px] font-medium uppercase tracking-wider text-ink-faint">
          Quick Actions
        </div>
        <nav className="space-y-0.5">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition",
                  isActive
                    ? "bg-surface-subtle text-ink"
                    : "text-ink-muted hover:bg-surface-subtle hover:text-ink"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-auto border-t border-line px-5 py-4 space-y-2">
        {user && (
          <div className="rounded-xl bg-surface-subtle px-3 py-2 text-xs text-ink-muted">
            <div className="font-medium text-ink">{user.email}</div>
            <button className="mt-1 text-ink-muted hover:text-ink" onClick={() => signOut()}>
              Sign out
            </button>
          </div>
        )}
        <div className="flex items-center gap-2 rounded-xl bg-surface-subtle px-3 py-2.5">
          <Tag className="h-4 w-4 text-ink-muted" />
          <div className="text-xs text-ink-muted">
            FBM auto-sync at <span className="font-medium text-ink">-10%</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
