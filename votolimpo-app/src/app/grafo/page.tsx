import type { Metadata } from "next";
import GraphVisualization from "@/components/GraphVisualization";
import type { GraphData } from "@/types";

export const revalidate = 0;

export const metadata: Metadata = {
  title: "Mapa de Partidos",
  description: "Visualizacao dos candidatos agrupados por partido",
};

async function fetchGraphData(): Promise<GraphData> {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : "http://localhost:3000";

  const res = await fetch(`${baseUrl}/api/graph`, {
    next: { revalidate: 0 },
  });

  if (!res.ok) throw new Error(`Graph API error: ${res.status}`);
  return res.json();
}

export default async function GrafoPage() {
  let graphData: GraphData;
  let politicians = 0;
  let parties = 0;
  let totalEdges = 0;

  try {
    graphData = await fetchGraphData();
    politicians = graphData.nodes.filter((n) => n.type === "politician").length;
    parties = graphData.nodes.filter((n) => n.type === "entity").length;
    totalEdges = graphData.edges.length;
  } catch (error) {
    console.error("[GrafoPage] Graph API error:", error);
    graphData = { nodes: [], edges: [] };
  }

  return (
    <div className="flex flex-col h-[calc(100vh-130px)] min-h-[600px]">
      {/* Header */}
      <div className="border-b border-[#1A1A1A] px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#FAFAFA]">Mapa de Partidos</h1>
            <p className="mt-1 text-sm text-[#6B7280]">
              Visualize os candidatos agrupados por partido
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded-full border-2 border-emerald-400 bg-emerald-400/10" />
              <span className="text-xs text-[#6B7280]">{politicians} candidatos</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded border border-[#6B7280] bg-[#1A1A1A]" />
              <span className="text-xs text-[#6B7280]">{parties} partidos</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-px w-4 bg-[#6B7280]" />
              <span className="text-xs text-[#6B7280]">{totalEdges} filiacoes</span>
            </div>
          </div>
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 p-4">
        <GraphVisualization data={graphData} />
      </div>
    </div>
  );
}
