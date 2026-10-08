import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const filter = request.nextUrl.searchParams.get("filter") || "pending";

    let whereClause: string;
    if (filter === "pending") {
      whereClause = `
        WHERE ar.id IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM help_core.review_actions ra
          WHERE ra.analysis_result_id = ar.id
        )
      `;
    } else {
      whereClause = `WHERE ar.id IS NOT NULL`;
    }

    const query = `
      SELECT
        a.id,
        a.title,
        a.area,
        ar.overall_score,
        ar.priority_level,
        ar.id as analysis_id,
        (
          SELECT ra.action FROM help_core.review_actions ra
          WHERE ra.analysis_result_id = ar.id
          ORDER BY ra.created_at DESC LIMIT 1
        ) as review_status
      FROM help_core.articles a
      JOIN help_core.analysis_results ar ON ar.article_id = a.id
      ${whereClause}
      ORDER BY
        CASE ar.priority_level
          WHEN 'critical' THEN 1
          WHEN 'high' THEN 2
          WHEN 'medium' THEN 3
          WHEN 'low' THEN 4
          ELSE 5
        END,
        ar.overall_score ASC NULLS LAST
      LIMIT 100
    `;

    const articles = await prisma.$queryRawUnsafe(query) as Array<Record<string, unknown>>;

    return NextResponse.json({
      articles: articles.map((a: Record<string, unknown>) => ({
        id: Number(a.id),
        title: a.title,
        area: a.area,
        overall_score: a.overall_score != null ? Number(a.overall_score) : null,
        priority_level: a.priority_level,
        analysis_id: Number(a.analysis_id),
        review_status: a.review_status || null,
      })),
    });
  } catch (error) {
    console.error("Review queue error:", error);
    return NextResponse.json({ error: "Erro ao carregar fila de revisao" }, { status: 500 });
  }
}
