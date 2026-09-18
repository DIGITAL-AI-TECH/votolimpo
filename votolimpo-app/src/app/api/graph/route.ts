import { NextResponse } from "next/server";
import {
  getEntityFilters,
  listEntities,
  countEntities,
  entityToPolitician,
} from "@/lib/nc-api";
import type { GraphData, GraphNode, GraphEdge } from "@/types";

export async function GET() {
  try {
    // Get all parties and states
    const filters = await getEntityFilters({
      type: "candidate",
      active: true,
    });

    const parties = filters.parties || [];

    // Get counts per party in parallel (top 30 parties max)
    const topParties = parties.slice(0, 30);
    const partyCounts = await Promise.all(
      topParties.map(async (party) => {
        const count = await countEntities({
          type: "candidate",
          active: true,
          party,
        });
        return { party, count };
      })
    );

    // Sort by count desc and take top 20
    const sortedParties = partyCounts
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);

    // Fetch top 5 politicians per party (top 10 parties only for perf)
    const topPartiesForDetail = sortedParties.slice(0, 10);
    const partyPoliticians = await Promise.all(
      topPartiesForDetail.map(async ({ party }) => {
        const entities = await listEntities({
          type: "candidate",
          active: true,
          party,
          limit: 5,
          order_by: "article_count",
          order_dir: "desc",
        });
        return {
          party,
          politicians: entities.map((e) => entityToPolitician(e)),
        };
      })
    );

    // Build party nodes
    const partyNodes: GraphNode[] = sortedParties.map(({ party, count }) => ({
      id: `party-${party}`,
      type: "entity" as const,
      label: `${party} (${count})`,
      entityType: "organization",
    }));

    // Build politician nodes from top politicians per party
    const politicianNodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];

    for (const { party, politicians } of partyPoliticians) {
      for (const p of politicians) {
        politicianNodes.push({
          id: p.id,
          type: "politician" as const,
          label: p.name,
          slug: p.slug,
          party: p.party,
          partyColor: p.partyColor,
          score: p.score,
        });
        edges.push({
          id: `rel-${p.id}-${party}`,
          source: p.id,
          target: `party-${party}`,
          type: "business_partner" as const,
          label: "filiado",
        });
      }
    }

    const graphData: GraphData = {
      nodes: [...politicianNodes, ...partyNodes],
      edges,
    };

    const response = NextResponse.json(graphData);
    response.headers.set(
      "Cache-Control",
      "public, s-maxage=600, stale-while-revalidate=1800"
    );
    return response;
  } catch (error) {
    console.error("[api/graph] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch graph data" },
      { status: 502 }
    );
  }
}
