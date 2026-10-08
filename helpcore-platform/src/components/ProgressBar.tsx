interface ProgressBarProps {
  processed: number;
  total: number;
  label?: string;
}

export function ProgressBar({ processed, total, label }: ProgressBarProps) {
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <div>
      {label && (
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="text-[#9EA5AC]">{label}</span>
          <span className="font-semibold text-white">
            {processed.toLocaleString("pt-BR")} / {total.toLocaleString("pt-BR")} ({pct}%)
          </span>
        </div>
      )}
      <div className="h-3 w-full overflow-hidden rounded-full bg-[#1A1A1A]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[#FF5722] to-[#FFC978] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
