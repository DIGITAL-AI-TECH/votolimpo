import { NextResponse } from "next/server";
import { getEntityFilters } from "@/lib/nc-api";

export async function GET() {
  try {
    const filters = await getEntityFilters({
      type: "candidate",
      active: true,
    });

    return NextResponse.json(filters);
  } catch (error) {
    console.error("[api/filters] NC API error:", error);
    return NextResponse.json(
      { parties: [], states: [] },
      { status: 200 } // degrade gracefully — empty filters, not 502
    );
  }
}
