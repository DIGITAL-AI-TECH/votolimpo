import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { REVIEW_ACTIONS, type ReviewActionType } from "@/lib/constants";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const articleId = parseInt(id, 10);
    if (isNaN(articleId)) {
      return NextResponse.json({ error: "ID invalido" }, { status: 400 });
    }

    const body = await request.json();
    const { action, notes } = body as { action: string; notes?: string };

    if (!REVIEW_ACTIONS.includes(action as ReviewActionType)) {
      return NextResponse.json(
        { error: `Acao invalida. Use: ${REVIEW_ACTIONS.join(", ")}` },
        { status: 400 }
      );
    }

    if (action !== "approved" && (!notes || notes.trim().length === 0)) {
      return NextResponse.json(
        { error: "Notas sao obrigatorias para rejeicao ou revisao" },
        { status: 400 }
      );
    }

    // Find the latest analysis result for this article
    const analysis = await prisma.analysisResult.findFirst({
      where: { article_id: articleId },
      orderBy: { processed_at: "desc" },
    });

    if (!analysis) {
      return NextResponse.json(
        { error: "Artigo sem resultado de analise para revisar" },
        { status: 404 }
      );
    }

    const review = await prisma.reviewAction.create({
      data: {
        analysis_result_id: analysis.id,
        action: action,
        notes: notes?.trim() || null,
      },
    });

    return NextResponse.json({ review }, { status: 201 });
  } catch (error) {
    console.error("Review error:", error);
    return NextResponse.json({ error: "Erro ao registrar revisao" }, { status: 500 });
  }
}
