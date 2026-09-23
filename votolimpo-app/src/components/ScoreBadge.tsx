import type { FC } from "react";

interface ScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

function getScoreConfig(score: number) {
  if (score >= 80) return { label: "Excelente", desc: "Alta transparência", color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/30", ring: "bg-emerald-400" };
  if (score >= 60) return { label: "Bom", desc: "Boa transparência", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/30", ring: "bg-blue-400" };
  if (score >= 40) return { label: "Regular", desc: "Transparência moderada", color: "text-yellow-400", bg: "bg-yellow-400/10 border-yellow-400/30", ring: "bg-yellow-400" };
  if (score >= 20) return { label: "Preocupante", desc: "Baixa transparência", color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/30", ring: "bg-orange-400" };
  return { label: "Crítico", desc: "Transparência crítica", color: "text-red-400", bg: "bg-red-400/10 border-red-400/30", ring: "bg-red-400" };
}

const ND_CONFIG = {
  label: "Sem dados",
  desc: "Sem notícias analisadas",
  color: "text-[#6B7280]",
  bg: "bg-[#6B7280]/10 border-[#6B7280]/30",
  ring: "bg-[#6B7280]",
};

const sizeClasses = {
  sm: { container: "px-2 py-0.5", text: "text-xs", score: "text-xs font-mono font-bold" },
  md: { container: "px-3 py-1", text: "text-sm", score: "text-sm font-mono font-bold" },
  lg: { container: "px-4 py-2", text: "text-base", score: "text-2xl font-mono font-bold" },
};

const ScoreBadge: FC<ScoreBadgeProps> = ({ score, size = "md", showLabel = false }) => {
  const isNull = score === null || score === undefined;
  const config = isNull ? ND_CONFIG : getScoreConfig(score);
  const sizes = sizeClasses[size];

  const tooltipText = isNull
    ? "Sem notícias analisadas ainda. Saiba mais em Como Funciona."
    : `Índice de Transparência: ${score}/100 — ${config.desc}. Calculado por IA a partir de notícias públicas.`;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${config.bg} ${sizes.container} transition-all cursor-help`}
      title={tooltipText}
    >
      <span className={`h-2 w-2 rounded-full ${config.ring} flex-shrink-0`} />
      <span className={`${sizes.score} ${config.color}`}>{isNull ? "N/D" : score}</span>
      {showLabel && (
        <span className={`${sizes.text} ${config.color} opacity-80`}>{config.label}</span>
      )}
    </span>
  );
};

export default ScoreBadge;
