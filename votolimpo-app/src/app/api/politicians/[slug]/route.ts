import { NextResponse } from "next/server";
import {
  listEntities,
  getEntityArticles,
  getEntityStats,
  entityToPolitician,
  ncArticleToArticle,
} from "@/lib/nc-api";

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function GET(_request: Request, { params }: RouteParams) {
  try {
    const { slug } = await params;

    // Find entity by slug — NC search is name-based, so we search and match slug
    const entities = await listEntities({
      type: "candidate",
      active: true,
      limit: 100,
    });

    const entity = entities.find((e) => e.slug === slug);

    if (!entity) {
      return NextResponse.json(
        { error: "Politician not found" },
        { status: 404 }
      );
    }

    // Fetch articles and stats in parallel
    const [articlesRes, statsRes] = await Promise.all([
      getEntityArticles(entity.id, { page_size: 50 }),
      getEntityStats(entity.id),
    ]);

    const politician = entityToPolitician(
      entity,
      statsRes.articles.total
    );

    const articles = articlesRes.items.map(ncArticleToArticle);

    return NextResponse.json({
      politician,
      articles,
      milestones: [], // NC doesn't have milestones yet
      relationships: [], // NC doesn't have relationships yet
    });
  } catch (error) {
    console.error("[api/politicians/[slug]] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch politician" },
      { status: 502 }
    );
  }
}
