"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

interface QualityRadarProps {
  clarity: number | null;
  structure: number | null;
  completeness: number | null;
  accuracy_signals: number | null;
  readability: number | null;
  overall_score: number | null;
}

export function QualityRadar({
  clarity,
  structure,
  completeness,
  accuracy_signals,
  readability,
  overall_score,
}: QualityRadarProps) {
  const data = [
    { axis: "Clareza", value: clarity ?? 0 },
    { axis: "Estrutura", value: structure ?? 0 },
    { axis: "Completude", value: completeness ?? 0 },
    { axis: "Precisão", value: accuracy_signals ?? 0 },
    { axis: "Legibilidade", value: readability ?? 0 },
  ];

  return (
    <div className="flex items-center gap-6">
      <div className="h-[220px] w-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
            <PolarGrid stroke="#1F1F1F" />
            <PolarAngleAxis
              dataKey="axis"
              tick={{ fill: "#9EA5AC", fontSize: 11 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: "#9EA5AC", fontSize: 10 }}
              tickCount={3}
            />
            <Radar
              dataKey="value"
              stroke="#FF5722"
              fill="#FF5722"
              fillOpacity={0.25}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      {overall_score != null && (
        <div className="text-center">
          <p className="text-sm text-[#9EA5AC]">Score Geral</p>
          <p className="text-4xl font-bold text-white">
            {Number(overall_score).toFixed(0)}
          </p>
          <p className="text-xs text-[#9EA5AC]">/ 100</p>
        </div>
      )}
    </div>
  );
}
