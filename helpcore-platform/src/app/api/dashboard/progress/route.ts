import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    // Total articles
    const totalArticles = await prisma.article.count();

    // Count processed (has analysis_result)
    const processedCount = await prisma.analysisResult.count();

    // Count with errors (priority_level null but result exists — indicates parsing issue)
    // For now, "not_processed" = total - processed
    const notProcessed = totalArticles - processedCount;

    // By area breakdown
    const byAreaRaw = await prisma.$queryRaw<
      Array<{ area: string; total: bigint; processed: bigint }>
    >`
      SELECT
        a.area,
        COUNT(*)::bigint as total,
        COUNT(ar.id)::bigint as processed
      FROM help_core.articles a
      LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
      GROUP BY a.area
      ORDER BY COUNT(*) DESC
    `;

    const byArea = byAreaRaw.map((r: { area: string; total: bigint; processed: bigint }) => ({
      area: r.area,
      total: Number(r.total),
      processed: Number(r.processed),
    }));

    // Cost from PE stats (query processing_engine schema)
    let costUsd = 0;
    try {
      const costResult = await prisma.$queryRaw<Array<{ total_cost: number }>>`
        SELECT COALESCE(SUM(cost_usd), 0)::float as total_cost
        FROM processing_engine.items
        WHERE pipeline_id IN (
          SELECT id FROM processing_engine.pipelines WHERE slug LIKE 'helpcore%'
        )
      `;
      costUsd = costResult[0]?.total_cost || 0;
    } catch {
      // If PE tables not accessible, cost stays 0
    }

    // Avg processing duration estimate (from PE if available)
    const avgDurationMs = 3200; // Default estimate

    // Estimated remaining hours
    const estimatedRemainingHours =
      notProcessed > 0 ? (notProcessed * avgDurationMs) / (1000 * 60 * 60) : 0;

    return NextResponse.json({
      total_articles: totalArticles,
      by_status: {
        not_processed: notProcessed,
        processed: processedCount,
        error: 0,
      },
      by_area: byArea,
      cost_usd: Math.round(costUsd * 100) / 100,
      avg_duration_ms: avgDurationMs,
      estimated_remaining_hours: Math.round(estimatedRemainingHours * 10) / 10,
      last_updated: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Dashboard progress error:", error);
    return NextResponse.json(
      { error: "Erro ao carregar dados do dashboard" },
      { status: 500 }
    );
  }
}
