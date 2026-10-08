import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { PAGINATION } from "@/lib/constants";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const area = searchParams.get("area");
    const search = searchParams.get("search");
    const priority = searchParams.get("priority");
    const scoreMin = searchParams.get("score_min");
    const scoreMax = searchParams.get("score_max");
    const docType = searchParams.get("doc_type");
    const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
    const perPage = Math.min(
      PAGINATION.MAX_PER_PAGE,
      Math.max(1, parseInt(searchParams.get("per_page") || String(PAGINATION.DEFAULT_PER_PAGE), 10))
    );
    const offset = (page - 1) * perPage;

    // Build WHERE conditions
    const conditions: string[] = [];
    const params: unknown[] = [];
    let paramIdx = 1;

    if (area) {
      conditions.push(`a.area = $${paramIdx++}`);
      params.push(area);
    }

    let searchParamIdx = 0;
    if (search) {
      searchParamIdx = paramIdx;
      conditions.push(`to_tsvector('portuguese', COALESCE(a.title,'') || ' ' || COALESCE(a.content,'')) @@ plainto_tsquery('portuguese', $${paramIdx++})`);
      params.push(search);
    }

    if (priority) {
      conditions.push(`ar.priority_level = $${paramIdx++}`);
      params.push(priority);
    }

    if (scoreMin) {
      conditions.push(`ar.overall_score >= $${paramIdx++}`);
      params.push(parseFloat(scoreMin));
    }

    if (scoreMax) {
      conditions.push(`ar.overall_score <= $${paramIdx++}`);
      params.push(parseFloat(scoreMax));
    }

    if (docType) {
      conditions.push(`ar.doc_type = $${paramIdx++}`);
      params.push(docType);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

    // Highlight snippet for search
    const highlightCol = search
      ? `, ts_headline('portuguese', COALESCE(a.content, ''), plainto_tsquery('portuguese', $${searchParamIdx}), 'MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>') as highlight`
      : `, '' as highlight`;

    // Count query
    const countQuery = `
      SELECT COUNT(*)::int as total
      FROM help_core.articles a
      LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
      ${whereClause}
    `;

    // Data query
    const dataQuery = `
      SELECT
        a.id, a.title, a.area, a.lista, a.classification, a.modified_date,
        CASE WHEN ar.id IS NOT NULL THEN true ELSE false END as is_processed,
        ar.overall_score,
        ar.priority_level
        ${highlightCol}
      FROM help_core.articles a
      LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
      ${whereClause}
      ORDER BY a.id ASC
      LIMIT $${paramIdx++} OFFSET $${paramIdx++}
    `;

    const countParams = [...params];
    const dataParams = [...params, perPage, offset];

    const [countResult, articles] = await Promise.all([
      prisma.$queryRawUnsafe(countQuery, ...countParams) as Promise<Array<{ total: number }>>,
      prisma.$queryRawUnsafe(dataQuery, ...dataParams) as Promise<Array<Record<string, unknown>>>,
    ]);

    const total = countResult[0]?.total || 0;

    return NextResponse.json({
      articles: articles.map((a: Record<string, unknown>) => ({
        id: Number(a.id),
        title: a.title,
        area: a.area,
        lista: a.lista,
        classification: a.classification,
        modified_date: a.modified_date,
        is_processed: a.is_processed,
        overall_score: a.overall_score ? Number(a.overall_score) : null,
        priority_level: a.priority_level,
        highlight: a.highlight || "",
      })),
      pagination: {
        page,
        per_page: perPage,
        total,
        total_pages: Math.ceil(total / perPage),
      },
    });
  } catch (error) {
    console.error("Articles error:", error);
    return NextResponse.json({ error: "Erro ao carregar artigos" }, { status: 500 });
  }
}
