import { NextResponse } from "next/server";
import {
  listEntities,
  listArticles,
  entityToPolitician,
  ncArticleToArticle,
} from "@/lib/nc-api";

export const dynamic = "force-dynamic";

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

    // Sort politicians by relevance: exact > starts-with > article count
    const qLower = q.toLowerCase();
    politicians.sort((a, b) => {
      const aName = a.name.toLowerCase();
      const bName = b.name.toLowerCase();
      const aExact = aName === qLower ? 0 : 1;
      const bExact = bName === qLower ? 0 : 1;
      if (aExact !== bExact) return aExact - bExact;
      const aStarts = aName.startsWith(qLower) ? 0 : 1;
      const bStarts = bName.startsWith(qLower) ? 0 : 1;
      if (aStarts !== bStarts) return aStarts - bStarts;
      return (b.articleCount ?? 0) - (a.articleCount ?? 0);
    });

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
