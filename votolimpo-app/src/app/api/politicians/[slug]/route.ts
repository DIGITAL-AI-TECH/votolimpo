import { NextResponse } from "next/server";
import { unstable_noStore } from "next/cache";
import {
  getEntityBySlug,
  getEntityArticles,
  getEntityStats,
  entityToPolitician,
  ncArticleToArticle,
  type NCEntityScore,
} from "@/lib/nc-api";

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: RouteParams) {
  unstable_noStore();
  try {
    const { slug } = await params;

    // Fetch entity directly by slug (no N+1 fallback needed)
    let entityData;
    try {
      entityData = await getEntityBySlug(slug);
    } catch {
      return NextResponse.json(
        { error: "Politician not found" },
        { status: 404 }
      );
    }

    // Fetch articles and stats in parallel
    const [articlesRes, statsRes] = await Promise.all([
      getEntityArticles(entityData.id, { page_size: 50 }),
      getEntityStats(entityData.id),
    ]);

    const politician = entityToPolitician(entityData, {
      entity_id: entityData.id,
      score: entityData.score,
      max_severity: entityData.max_severity,
      article_count: entityData.article_count,
    } as NCEntityScore);

    const articles = articlesRes.items.map(ncArticleToArticle);

    return NextResponse.json({
      politician,
      articles,
      milestones: [],     // NC doesn't have milestones yet
      relationships: [],  // NC doesn't have relationships yet
    });
  } catch (error) {
    console.error("[api/politicians/[slug]] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch politician" },
      { status: 502 }
    );
  }
}
