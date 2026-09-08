import type { FC } from "react";
import type { Severity } from "@/types";

interface SeverityBadgeProps {
  severity: Severity;
  size?: "sm" | "md";
}

const SEVERITY_CONFIG: Record<Severity, { label: string; classes: string }> = {
  critical: { label: "Crítico", classes: "bg-red-400/10 text-red-400 border-red-400/30" },
  high: { label: "Alto", classes: "bg-orange-400/10 text-orange-400 border-orange-400/30" },
  medium: { label: "Médio", classes: "bg-yellow-400/10 text-yellow-400 border-yellow-400/30" },
  low: { label: "Baixo", classes: "bg-blue-400/10 text-blue-400 border-blue-400/30" },
  info: { label: "Info", classes: "bg-gray-400/10 text-gray-400 border-gray-400/30" },
};

const SeverityBadge: FC<SeverityBadgeProps> = ({ severity, size = "sm" }) => {
  const config = SEVERITY_CONFIG[severity];
  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${config.classes} ${sizeClass}`}
    >
      {config.label}
    </span>
  );
};

export default SeverityBadge;
