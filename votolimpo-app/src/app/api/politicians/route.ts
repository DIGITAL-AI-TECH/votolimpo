import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import { listEntities, entityToPolitician } from "@/lib/nc-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  unstable_noStore();
  try {
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get("page") || "1");
    const pageSize = parseInt(searchParams.get("pageSize") || "20");
    const party = searchParams.get("party") || undefined;
    const uf = searchParams.get("uf") || undefined;
    const search = searchParams.get("search") || undefined;

    // NC API uses skip/limit pagination
    const skip = (page - 1) * pageSize;

    const entities = await listEntities({
      type: "candidate",
      search,
      active: true,
      skip,
      limit: pageSize,
    });

    let politicians = entities.map((e) => entityToPolitician(e));

    // Client-side filter by party/uf since NC API doesn't support these filters directly
    if (party) politicians = politicians.filter((p) => p.party === party);
    if (uf) politicians = politicians.filter((p) => p.uf === uf);

    return NextResponse.json({
      data: politicians,
      total: politicians.length,
      page,
      pageSize,
      totalPages: Math.ceil(politicians.length / pageSize),
    });
  } catch (error) {
    console.error("[api/politicians] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch politicians" },
      { status: 502 }
    );
  }
}
