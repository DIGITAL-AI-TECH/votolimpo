"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ProgressBar";
import { AUTO_REFRESH_INTERVAL } from "@/lib/constants";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";

interface AnalyticsData {
  by_category: Array<{ name: string; value: number }>;
  by_doc_type: Array<{ name: string; value: number }>;
  score_histogram: Array<{ bucket: string; count: number }>;
  areas_ranked: Array<{ area: string; total: number; processed: number; avg_score: number | null }>;
}

interface DashboardData {
  total_articles: number;
  by_status: {
    not_processed: number;
    processed: number;
    error: number;
  };
  by_area: Array<{ area: string; total: number; processed: number }>;
  cost_usd: number;
  avg_duration_ms: number;
  estimated_remaining_hours: number;
  last_updated: string;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [progressRes, analyticsRes] = await Promise.all([
        fetch("/api/dashboard/progress"),
        fetch("/api/analytics/distribution"),
      ]);
      if (progressRes.ok) setData(await progressRes.json());
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, AUTO_REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading || !data) {
    return (
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <div className="h-20" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const pct = data.total_articles > 0
    ? Math.round((data.by_status.processed / data.total_articles) * 100)
    : 0;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <span className="text-xs text-[#9EA5AC]">
          Atualizado: {new Date(data.last_updated).toLocaleTimeString("pt-BR")}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#9EA5AC]">
            Total de Artigos
          </p>
          <p className="mt-2 text-3xl font-bold text-white">
            {data.total_articles.toLocaleString("pt-BR")}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#9EA5AC]">
            Processados
          </p>
          <p className="mt-2 text-3xl font-bold text-[#22C55E]">
            {data.by_status.processed.toLocaleString("pt-BR")}
          </p>
          <p className="mt-1 text-sm text-[#9EA5AC]">{pct}% concluído</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#9EA5AC]">
            Custo Acumulado
          </p>
          <p className="mt-2 text-3xl font-bold text-[#FF5722]">
            ${data.cost_usd.toFixed(2)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#9EA5AC]">
            Tempo Restante
          </p>
          <p className="mt-2 text-3xl font-bold text-white">
            {data.estimated_remaining_hours > 0
              ? `${data.estimated_remaining_hours.toFixed(1)}h`
              : "Concluído"}
          </p>
        </Card>
      </div>

      {/* Progress Bar */}
      <Card>
        <CardHeader>
          <CardTitle>Progresso Geral</CardTitle>
        </CardHeader>
        <ProgressBar
          processed={data.by_status.processed}
          total={data.total_articles}
          label="Artigos processados"
        />
      </Card>

      {/* Area Breakdown Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Progresso por Área Operacional</CardTitle>
        </CardHeader>
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data.by_area.slice(0, 15).map((a: { area: string; total: number; processed: number }) => ({ ...a, not_processed: a.total - a.processed }))}
              layout="vertical"
              margin={{ left: 120 }}
            >
              <XAxis type="number" stroke="#9EA5AC" fontSize={12} />
              <YAxis
                type="category"
                dataKey="area"
                stroke="#9EA5AC"
                fontSize={11}
                width={120}
                tick={{ fill: "#D4D8DD" }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#151515",
                  border: "1px solid #1F1F1F",
                  borderRadius: "12px",
                  color: "#D4D8DD",
                }}
              />
              <Bar dataKey="processed" name="Processados" stackId="a" fill="#FF5722" radius={[0, 0, 0, 0]} />
              <Bar
                dataKey="not_processed"
                name="Pendentes"
                stackId="a"
                fill="#1A1A1A"
                radius={[0, 4, 4, 0]}
              >
                {data.by_area.slice(0, 15).map((_, i) => (
                  <Cell key={i} fill="#1A1A1A" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      {/* Analytics Section */}
      {analytics && (
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Category Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Distribuicao por Categoria</CardTitle>
              </CardHeader>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={analytics.by_category.slice(0, 8)}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      labelLine={{ stroke: "#9EA5AC" }}
                    >
                      {analytics.by_category.slice(0, 8).map((_, i) => (
                        <Cell
                          key={i}
                          fill={PIE_COLORS[i % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#151515",
                        border: "1px solid #1F1F1F",
                        borderRadius: "12px",
                        color: "#D4D8DD",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Doc Type Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Distribuicao por Tipo de Documento</CardTitle>
              </CardHeader>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={analytics.by_doc_type.slice(0, 8)}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      labelLine={{ stroke: "#9EA5AC" }}
                    >
                      {analytics.by_doc_type.slice(0, 8).map((_, i) => (
                        <Cell
                          key={i}
                          fill={PIE_COLORS[i % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#151515",
                        border: "1px solid #1F1F1F",
                        borderRadius: "12px",
                        color: "#D4D8DD",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          {/* Score Histogram */}
          <Card>
            <CardHeader>
              <CardTitle>Histograma de Score Geral</CardTitle>
            </CardHeader>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.score_histogram}>
                  <XAxis dataKey="bucket" stroke="#9EA5AC" fontSize={12} />
                  <YAxis stroke="#9EA5AC" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#151515",
                      border: "1px solid #1F1F1F",
                      borderRadius: "12px",
                      color: "#D4D8DD",
                    }}
                  />
                  <Bar dataKey="count" name="Artigos" fill="#FF5722" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Areas Ranked Table */}
          <Card>
            <CardHeader>
              <CardTitle>Areas por Score Medio</CardTitle>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1F1F1F] text-left text-[#9EA5AC]">
                    <th className="pb-2 pr-4">Area</th>
                    <th className="pb-2 pr-4 text-right">Total</th>
                    <th className="pb-2 pr-4 text-right">Processados</th>
                    <th className="pb-2 text-right">Score Medio</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.areas_ranked.map((row) => (
                    <tr key={row.area} className="border-b border-[#1F1F1F]/50">
                      <td className="py-2 pr-4 text-white">{row.area}</td>
                      <td className="py-2 pr-4 text-right text-[#D4D8DD]">
                        {row.total.toLocaleString()}
                      </td>
                      <td className="py-2 pr-4 text-right text-[#D4D8DD]">
                        {row.processed.toLocaleString()}
                      </td>
                      <td className="py-2 text-right font-bold text-white">
                        {row.avg_score != null ? row.avg_score.toFixed(1) : "N/D"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

const PIE_COLORS = [
  "#FF5722", "#FFC978", "#FF8A65", "#E64A19",
  "#22C55E", "#3B82F6", "#A855F7", "#EC4899",
];
