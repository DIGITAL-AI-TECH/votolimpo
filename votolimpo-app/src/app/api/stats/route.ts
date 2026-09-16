import { NextResponse } from "next/server";
import { getGlobalStats, getVotoLimpoStats, ncStatsToStats } from "@/lib/nc-api";

export async function GET() {
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
