import { NextResponse } from "next/server";
import { listEntities, countEntities, entityToPolitician } from "@/lib/nc-api";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = Math.max(1, parseInt(searchParams.get("page") || "1") || 1);
    const pageSize = Math.min(100, Math.max(1, parseInt(searchParams.get("pageSize") || "20") || 20));
    const party = searchParams.get("party") || undefined;
    const uf = searchParams.get("uf") || undefined;
    const search = searchParams.get("search") || undefined;

    const skip = (page - 1) * pageSize;

    const [entities, total] = await Promise.all([
      listEntities({
        type: "candidate",
        search,
        active: true,
        party,
        state: uf,
        skip,
        limit: pageSize,
      }),
      countEntities({
        type: "candidate",
        active: true,
        search,
        party,
        state: uf,
      }),
    ]);

    const politicians = entities.map((e) => entityToPolitician(e));

    return NextResponse.json({
      data: politicians,
      total,
      page,
      pageSize,
      totalPages: Math.ceil(total / pageSize),
    });
  } catch (error) {
    console.error("[api/politicians] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch politicians" },
      { status: 502 }
    );
  }
}
