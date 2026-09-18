import { NextResponse } from "next/server";
import {
  listEntities,
  countEntities,
  entityToPolitician,
  type NCEntityWithScore,
} from "@/lib/nc-api";
import type { Politician } from "@/types";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = Math.max(1, parseInt(searchParams.get("page") || "1") || 1);
    const pageSize = Math.min(100, Math.max(1, parseInt(searchParams.get("pageSize") || "20") || 20));
    const sortBy = searchParams.get("sortBy") || "name";
    const sortOrder = searchParams.get("sortOrder") || "asc";
    const searchQuery = searchParams.get("search") || undefined;
    const party = searchParams.get("party") || undefined;
    const uf = searchParams.get("uf") || undefined;

    // Map frontend sort fields to backend order_by params
    const orderByMap: Record<string, string> = {
      name: "name",
      party: "party",
      uf: "state",
      articleCount: "article_count",
      score: "score",
    };
    const order_by = orderByMap[sortBy] || "name";
    const effectiveOrderBy = order_by;

    const skip = (page - 1) * pageSize;

    // Fetch one page from the NC backend and the total count in parallel
    const [entities, total] = await Promise.all([
      listEntities({
        type: "candidate",
        active: true,
        skip,
        limit: pageSize,
        search: searchQuery,
        party,
        state: uf,
        order_by: effectiveOrderBy,
        order_dir: sortOrder,
      }),
      countEntities({
        type: "candidate",
        active: true,
        search: searchQuery,
        party,
        state: uf,
      }),
    ]);

    // Map entities to Politician objects
    const politicians: Politician[] = entities.map((e) => {
      const enriched = e as unknown as NCEntityWithScore;
      return entityToPolitician(enriched, {
        entity_id: enriched.id,
        score: enriched.score ?? null,
        max_severity: enriched.max_severity ?? "info",
        article_count: enriched.article_count ?? 0,
      });
    });

    const response = NextResponse.json({
      data: politicians,
      total,
      page,
      pageSize,
      totalPages: Math.ceil(total / pageSize),
    });
    response.headers.set('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300');
    return response;
  } catch (error) {
    console.error("[api/ranking] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch ranking" },
      { status: 502 }
    );
  }
}
