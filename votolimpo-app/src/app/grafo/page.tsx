import type { Metadata } from "next";
import { listEntities, entityToPolitician } from "@/lib/nc-api";
import GraphVisualization from "@/components/GraphVisualization";
import type { GraphData, GraphNode, GraphEdge } from "@/types";

export const metadata: Metadata = {
  title: "Grafo de Vinculos",
  description: "Visualizacao interativa dos vinculos entre candidatos e partidos",
};

export const dynamic = "force-dynamic";
export const revalidate = 600;

export default async function GrafoPage() {
  let graphData: GraphData;
  let politicians = 0;
  let entities = 0;
  let totalEdges = 0;

  try {
    const ncEntities = await listEntities({
      type: "candidate",
      active: true,
      limit: 100,
    });

    const pols = ncEntities.map((e) => entityToPolitician(e));

    const politicianNodes: GraphNode[] = pols.map((p) => ({
      id: p.id,
      type: "politician" as const,
      label: p.name,
      slug: p.slug,
      party: p.party,
      partyColor: p.partyColor,
      score: p.score,
    }));

    const partySet = new Set(pols.map((p) => p.party));
    const partyNodes: GraphNode[] = [...partySet].map((party) => ({
      id: `party-${party}`,
      type: "entity" as const,
      label: party,
      entityType: "organization",
    }));

    const edges: GraphEdge[] = pols.map((p) => ({
      id: `rel-${p.id}-${p.party}`,
      source: p.id,
      target: `party-${p.party}`,
      type: "business_partner" as const,
      label: "filiado",
    }));

    graphData = {
      nodes: [...politicianNodes, ...partyNodes],
      edges,
    };

    politicians = politicianNodes.length;
    entities = partyNodes.length;
    totalEdges = edges.length;
  } catch (error) {
    console.error("[GrafoPage] NC API error:", error);
    graphData = { nodes: [], edges: [] };
  }

  return (
    <div className="flex flex-col h-[calc(100vh-130px)] min-h-[600px]">
      {/* Header */}
      <div className="border-b border-[#1A1A1A] px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#FAFAFA]">Grafo de Vinculos</h1>
            <p className="mt-1 text-sm text-[#6B7280]">
              Visualize as conexoes entre candidatos e partidos
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded-full border-2 border-emerald-400 bg-emerald-400/10" />
              <span className="text-xs text-[#6B7280]">{politicians} candidatos</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-3 w-3 rounded border border-[#6B7280] bg-[#1A1A1A]" />
              <span className="text-xs text-[#6B7280]">{entities} partidos</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5">
              <div className="h-px w-4 bg-[#6B7280]" />
              <span className="text-xs text-[#6B7280]">{totalEdges} vinculos</span>
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
