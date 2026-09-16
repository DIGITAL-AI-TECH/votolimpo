import { NextResponse } from "next/server";
import {
  listEntities,
  countEntities,
  entityToPolitician,
  type NCEntityWithScore,
} from "@/lib/nc-api";
import type { SortField, SortOrder, Politician } from "@/types";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = Math.max(1, parseInt(searchParams.get("page") || "1") || 1);
    const pageSize = Math.min(100, Math.max(1, parseInt(searchParams.get("pageSize") || "20") || 20));
    const sortBy = (searchParams.get("sortBy") || "name") as SortField;
    const sortOrder = (searchParams.get("sortOrder") || "asc") as SortOrder;
    const searchQuery = searchParams.get("search") || undefined;

    // NOTE: The NC backend does not support filtering by party or uf.
    // Party/UF filters are intentionally not forwarded to the backend —
    // see spec OUT-OF-SCOPE: "Filtros partido/UF server-side no ranking".

    const skip = (page - 1) * pageSize;

    // Fetch one page from the NC backend and the total count in parallel
    const [entities, total] = await Promise.all([
      listEntities({
        type: "candidate",
        active: true,
        skip,
        limit: pageSize,
        search: searchQuery,
      }),
      countEntities({
        type: "candidate",
        active: true,
        search: searchQuery,
      }),
    ]);

    // Map entities to Politician objects
    // score is loaded individually on /politico/[slug] to avoid N+1
    const politicians: Politician[] = entities.map((e) => {
      const enriched = e as unknown as NCEntityWithScore;
      return entityToPolitician(enriched, {
        entity_id: enriched.id,
        score: null,
        max_severity: "info",
        article_count: enriched.article_count ?? 0,
      });
    });

    // Client-side sort within the current page
    // (sort server-side is OUT-OF-SCOPE — NC backend has no order_by param)
    politicians.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case "name":
          comparison = a.name.localeCompare(b.name);
          break;
        case "score":
          comparison = a.score - b.score;
          break;
        case "articleCount":
          comparison = a.articleCount - b.articleCount;
          break;
        case "party":
          comparison = a.party.localeCompare(b.party);
          break;
        case "uf":
          comparison = a.uf.localeCompare(b.uf);
          break;
        default:
          comparison = a.name.localeCompare(b.name);
      }
      return sortOrder === "desc" ? -comparison : comparison;
    });

    return NextResponse.json({
      data: politicians,
      total,
      page,
      pageSize,
      totalPages: Math.ceil(total / pageSize),
    });
  } catch (error) {
    console.error("[api/ranking] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch ranking" },
      { status: 502 }
    );
  }
}
