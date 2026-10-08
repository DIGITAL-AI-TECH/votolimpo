import { Badge } from "@/components/ui/Badge";

interface ScoreBadgeProps {
  priority: string | null;
  score?: number | null;
}

export function ScoreBadge({ priority, score }: ScoreBadgeProps) {
  const variant = (priority as "critical" | "high" | "medium" | "low") || "default";
  const label = priority ? priority.charAt(0).toUpperCase() + priority.slice(1) : "N/D";

  return (
    <div className="flex items-center gap-2">
      <Badge variant={variant}>{label}</Badge>
      {score != null && (
        <span className="text-sm font-semibold text-white">
          {Number(score).toFixed(1)}
        </span>
      )}
    </div>
  );
}
