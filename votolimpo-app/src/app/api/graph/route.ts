import { NextResponse } from "next/server";
import { listEntities, entityToPolitician } from "@/lib/nc-api";
import type { GraphData, GraphNode, GraphEdge } from "@/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    // Fetch candidates to build graph nodes
    // NC API doesn't have relationship/graph data yet,
    // so we build a party-based graph from entities
    const entities = await listEntities({
      type: "candidate",
      active: true,
      limit: 100,
    });

    const politicians = entities.map((e) => entityToPolitician(e));

    // Build nodes from politicians
    const politicianNodes: GraphNode[] = politicians.map((p) => ({
      id: p.id,
      type: "politician" as const,
      label: p.name,
      slug: p.slug,
      party: p.party,
      partyColor: p.partyColor,
      score: p.score,
    }));

    // Build party nodes as entities
    const partySet = new Set(politicians.map((p) => p.party));
    const partyNodes: GraphNode[] = [...partySet].map((party) => ({
      id: `party-${party}`,
      type: "entity" as const,
      label: party,
      entityType: "organization",
    }));

    // Build edges: politician -> party
    const edges: GraphEdge[] = politicians.map((p) => ({
      id: `rel-${p.id}-${p.party}`,
      source: p.id,
      target: `party-${p.party}`,
      type: "business_partner" as const,
      label: "filiado",
    }));

    const graphData: GraphData = {
      nodes: [...politicianNodes, ...partyNodes],
      edges,
    };

    return NextResponse.json(graphData);
  } catch (error) {
    console.error("[api/graph] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch graph data" },
      { status: 502 }
    );
  }
}
