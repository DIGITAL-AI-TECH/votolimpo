import type { Metadata } from "next";
import { getGraphData } from "@/lib/mock-data";
import GraphVisualization from "@/components/GraphVisualization";

export const metadata: Metadata = {
  title: "Grafo de Vínculos",
  description: "Visualização interativa dos vínculos entre políticos e entidades brasileiras",
};

export default function GrafoPage() {
  const graphData = getGraphData();

  const totalEdges = graphData.edges.length;
  const politicians = graphData.nodes.filter((n) => n.type === "politician").length;
  const entities = graphData.nodes.filter((n) => n.type === "entity").length;

  return (
    <div className="flex flex-col h-[calc(100vh-130px)] min-h-[600px]">
      {/* Header */}
      <div className="border-b border-[#1A1A1A] px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#FAFAFA]">Grafo de Vínculos</h1>
            <p className="mt-1 text-sm text-[#6B7280]">
              Visualize as conexões entre políticos e entidades
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded-full border-2 border-emerald-400 bg-emerald-400/10" />
              <span className="text-xs text-[#6B7280]">{politicians} políticos</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded border border-[#6B7280] bg-[#1A1A1A]" />
              <span className="text-xs text-[#6B7280]">{entities} entidades</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-px w-4 bg-[#6B7280]" />
              <span className="text-xs text-[#6B7280]">{totalEdges} vínculos</span>
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
