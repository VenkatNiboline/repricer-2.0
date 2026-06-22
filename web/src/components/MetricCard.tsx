interface MetricCardProps {
  label: string;
  value: string;
  hint?: string;
  trend?: string;
}

export function MetricCard({ label, value, hint, trend }: MetricCardProps) {
  return (
    <div className="panel p-5">
      <div className="text-sm text-ink-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-ink">
        {value}
      </div>
      {(hint || trend) && (
        <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
          {trend && <span className="font-medium text-emerald-600">{trend}</span>}
          {hint}
        </div>
      )}
    </div>
  );
}
