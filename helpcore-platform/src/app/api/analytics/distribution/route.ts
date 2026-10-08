import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const [byCategory, byDocType, byPriority, scoreHistogram, areasRanked] =
      await Promise.all([
        prisma.$queryRawUnsafe(
          `SELECT COALESCE(category, 'N/D') as category, COUNT(*)::int as count
           FROM help_core.analysis_results
           GROUP BY category ORDER BY count DESC LIMIT 20`
        ) as Promise<Array<{ category: string; count: number }>>,
        prisma.$queryRawUnsafe(
          `SELECT COALESCE(doc_type, 'N/D') as doc_type, COUNT(*)::int as count
           FROM help_core.analysis_results
           GROUP BY doc_type ORDER BY count DESC LIMIT 20`
        ) as Promise<Array<{ doc_type: string; count: number }>>,
        prisma.$queryRawUnsafe(
          `SELECT COALESCE(priority_level, 'N/D') as priority_level, COUNT(*)::int as count
           FROM help_core.analysis_results
           GROUP BY priority_level ORDER BY count DESC`
        ) as Promise<Array<{ priority_level: string; count: number }>>,
        prisma.$queryRawUnsafe(
          `SELECT
             CASE
               WHEN overall_score < 10 THEN '0-9'
               WHEN overall_score < 20 THEN '10-19'
               WHEN overall_score < 30 THEN '20-29'
               WHEN overall_score < 40 THEN '30-39'
               WHEN overall_score < 50 THEN '40-49'
               WHEN overall_score < 60 THEN '50-59'
               WHEN overall_score < 70 THEN '60-69'
               WHEN overall_score < 80 THEN '70-79'
               WHEN overall_score < 90 THEN '80-89'
               ELSE '90-100'
             END as bucket,
             COUNT(*)::int as count
           FROM help_core.analysis_results
           WHERE overall_score IS NOT NULL
           GROUP BY bucket
           ORDER BY bucket`
        ) as Promise<Array<{ bucket: string; count: number }>>,
        prisma.$queryRawUnsafe(
          `SELECT
             a.area,
             COUNT(*)::int as total,
             COUNT(ar.id)::int as processed,
             ROUND(AVG(ar.overall_score)::numeric, 1) as avg_score
           FROM help_core.articles a
           LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
           GROUP BY a.area
           ORDER BY avg_score ASC NULLS LAST`
        ) as Promise<Array<{ area: string; total: number; processed: number; avg_score: number }>>,
      ]);

    return NextResponse.json({
      by_category: byCategory.map((r) => ({ name: r.category, value: Number(r.count) })),
      by_doc_type: byDocType.map((r) => ({ name: r.doc_type, value: Number(r.count) })),
      by_priority: byPriority.map((r) => ({ name: r.priority_level, value: Number(r.count) })),
      score_histogram: scoreHistogram.map((r) => ({
        bucket: r.bucket,
        count: Number(r.count),
      })),
      areas_ranked: areasRanked.map((r) => ({
        area: r.area,
        total: Number(r.total),
        processed: Number(r.processed),
        avg_score: r.avg_score != null ? Number(r.avg_score) : null,
      })),
    });
  } catch (error) {
    console.error("Analytics error:", error);
    return NextResponse.json({ error: "Erro ao carregar analytics" }, { status: 500 });
  }
}
