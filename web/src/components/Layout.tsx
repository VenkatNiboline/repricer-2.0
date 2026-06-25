import { ReactNode } from "react";
import { MarketplaceSelector } from "./MarketplaceSelector";
import { Sidebar } from "./Sidebar";

interface LayoutProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function Layout({ title, subtitle, actions, children }: LayoutProps) {
  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 border-b border-line bg-white/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-8 py-5">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-ink">
                {title}
              </h1>
              {subtitle && (
                <p className="mt-0.5 text-sm text-ink-muted">{subtitle}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <MarketplaceSelector />
              {actions && <div className="flex items-center gap-2">{actions}</div>}
            </div>
          </div>
        </header>
        <main className="flex-1 px-8 py-6">{children}</main>
      </div>
    </div>
  );
}
