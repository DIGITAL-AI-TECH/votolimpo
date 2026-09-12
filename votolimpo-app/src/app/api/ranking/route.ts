import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import { listEntities, entityToPolitician } from "@/lib/nc-api";
import type { SortField, SortOrder, Politician } from "@/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  unstable_noStore();
  try {
    const { searchParams } = new URL(request.url);
    const party = searchParams.get("party") || undefined;
    const uf = searchParams.get("uf") || undefined;
    const page = parseInt(searchParams.get("page") || "1");
    const pageSize = parseInt(searchParams.get("pageSize") || "20");
    const sortBy = (searchParams.get("sortBy") || "score") as SortField;
    const sortOrder = (searchParams.get("sortOrder") || "asc") as SortOrder;

    // Fetch all candidates for ranking (NC max limit is 100 per page)
    const entities = await listEntities({
      type: "candidate",
      active: true,
      limit: 100,
    });

    let politicians: Politician[] = entities.map((e) =>
      entityToPolitician(e)
    );

    // Apply filters
    if (party) politicians = politicians.filter((p) => p.party === party);
    if (uf) politicians = politicians.filter((p) => p.uf === uf);

    // Sort
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

    const total = politicians.length;
    const start = (page - 1) * pageSize;
    const data = politicians.slice(start, start + pageSize);

    return NextResponse.json({
      data,
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
