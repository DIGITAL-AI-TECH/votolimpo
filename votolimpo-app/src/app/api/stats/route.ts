import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import { getGlobalStats, ncStatsToStats } from "@/lib/nc-api";

export const dynamic = "force-dynamic";

export async function GET() {
  unstable_noStore();
  try {
    const ncStats = await getGlobalStats();
    const stats = ncStatsToStats(ncStats);
    return NextResponse.json(stats);
  } catch (error) {
    console.error("[api/stats] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch stats" },
      { status: 502 }
    );
  }
}
