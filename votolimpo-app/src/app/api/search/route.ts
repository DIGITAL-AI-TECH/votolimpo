import { NextResponse } from "next/server";
import {
  listEntities,
  listArticles,
  entityToPolitician,
  ncArticleToArticle,
} from "@/lib/nc-api";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get("q") || "";

    if (!q.trim()) {
      return NextResponse.json({
        politicians: [],
        articles: [],
        total: 0,
      });
    }

    // Search entities and articles in parallel
    const [entities, articlesRes] = await Promise.all([
      listEntities({ search: q, type: "candidate", active: true, limit: 20 }),
      listArticles({ q, status: "processed", page_size: 10 }),
    ]);

    const politicians = entities.map((e) => entityToPolitician(e));
    const articles = articlesRes.items.map(ncArticleToArticle);

    return NextResponse.json({
      politicians,
      articles,
      total: politicians.length + articles.length,
    });
  } catch (error) {
    console.error("[api/search] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to search" },
      { status: 502 }
    );
  }
}
