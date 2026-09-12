import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import { listArticles, ncArticleToArticle } from "@/lib/nc-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  unstable_noStore();
  try {
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get("page") || "1");
    const pageSize = parseInt(searchParams.get("pageSize") || "20");
    const status = searchParams.get("status") || "processed";
    const q = searchParams.get("q") || undefined;
    const entityId = searchParams.get("politicianId") || undefined;

    const result = await listArticles({
      page,
      page_size: pageSize,
      status,
      q,
      entity_id: entityId ? parseInt(entityId) : undefined,
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
