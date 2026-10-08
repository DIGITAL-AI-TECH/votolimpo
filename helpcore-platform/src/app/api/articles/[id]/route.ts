import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const articleId = parseInt(id, 10);
    if (isNaN(articleId)) {
      return NextResponse.json({ error: "ID inválido" }, { status: 400 });
    }

    const article = await prisma.article.findUnique({
      where: { id: articleId },
      include: {
        analysis_results: {
          take: 1,
          orderBy: { processed_at: "desc" },
          include: {
            review_actions: {
              take: 1,
              orderBy: { created_at: "desc" },
            },
          },
        },
      },
    });

    if (!article) {
      return NextResponse.json({ error: "Artigo não encontrado" }, { status: 404 });
    }

    const analysis = article.analysis_results[0] || null;
    const lastReview = analysis?.review_actions[0] || null;

    // Determine review status
    let reviewStatus = "pending";
    if (lastReview) {
      reviewStatus = lastReview.action;
    }

    return NextResponse.json({
      article: {
        id: article.id,
        title: article.title,
        subtitle: article.subtitle,
        area: article.area,
        lista: article.lista,
        content: article.content,
        classification: article.classification,
        modified_date: article.modified_date,
        links: article.links,
        source_url: article.source_url,
      },
      analysis: analysis
        ? {
            doc_type: analysis.doc_type,
            category: analysis.category,
            subcategory: analysis.subcategory,
            target_audience: analysis.target_audience,
            key_topics: analysis.key_topics,
            overall_score: analysis.overall_score ? Number(analysis.overall_score) : null,
            priority_level: analysis.priority_level,
            clarity: analysis.clarity ? Number(analysis.clarity) : null,
            structure: analysis.structure ? Number(analysis.structure) : null,
            completeness: analysis.completeness ? Number(analysis.completeness) : null,
            accuracy_signals: analysis.accuracy_signals ? Number(analysis.accuracy_signals) : null,
            readability: analysis.readability ? Number(analysis.readability) : null,
            steps: analysis.steps,
            improvement_suggestions: analysis.improvement_suggestions,
            markdown_content: analysis.markdown_content,
            processed_at: analysis.processed_at,
          }
        : null,
      review_status: reviewStatus,
      last_review: lastReview
        ? {
            action: lastReview.action,
            notes: lastReview.notes,
            created_at: lastReview.created_at,
          }
        : null,
    });
  } catch (error) {
    console.error("Article detail error:", error);
    return NextResponse.json({ error: "Erro interno" }, { status: 500 });
  }
}
