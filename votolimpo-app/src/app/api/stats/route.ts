import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import { getGlobalStats, getVotoLimpoStats, ncStatsToStats } from "@/lib/nc-api";

export const dynamic = "force-dynamic";

export async function GET() {
  unstable_noStore();
  try {
    const [ncStats, vlStats] = await Promise.all([
      getGlobalStats(),
      getVotoLimpoStats(),
    ]);
    const stats = ncStatsToStats(ncStats, vlStats);
    return NextResponse.json(stats);
  } catch (error) {
    console.error("[api/stats] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch stats" },
      { status: 502 }
    );
  }
}
