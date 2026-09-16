import { NextResponse } from "next/server";
import { listArticles, ncArticleToArticle } from "@/lib/nc-api";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get("page") || "1");
    const pageSize = parseInt(searchParams.get("pageSize") || "20");
    const status = searchParams.get("status") || "processed";
    const q = searchParams.get("q") || undefined;
    const entityId = searchParams.get("politicianId") || undefined;

    const severity = searchParams.get("severity") || undefined;
    const isPolitical = searchParams.get("is_political") || undefined;

    const result = await listArticles({
      page,
      page_size: pageSize,
      status,
      q,
      entity_id: entityId ? parseInt(entityId) : undefined,
      severity,
      is_political: isPolitical !== undefined ? isPolitical === "true" : undefined,
    });

    const articles = result.items.map(ncArticleToArticle);

    return NextResponse.json({
      data: articles,
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
      totalPages: result.pages,
    });
  } catch (error) {
    console.error("[api/articles] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch articles" },
      { status: 502 }
    );
  }
}
