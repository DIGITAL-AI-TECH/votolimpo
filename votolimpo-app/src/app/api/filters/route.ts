import { NextResponse } from "next/server";
import { getEntityFilters } from "@/lib/nc-api";

export async function GET() {
  try {
    const filters = await getEntityFilters({
      type: "candidate",
      active: true,
    });

    const response = NextResponse.json(filters);
    response.headers.set('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300');
    return response;
  } catch (error) {
    console.error("[api/filters] NC API error:", error);
    return NextResponse.json(
      { parties: [], states: [] },
      { status: 200 } // degrade gracefully — empty filters, not 502
    );
  }
}
