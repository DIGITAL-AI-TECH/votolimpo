import { NextResponse } from "next/server";
import {
  getEntityBySlug,
  getEntityArticles,
  getEntityMilestones,
  entityToPolitician,
  ncArticleToArticle,
  type NCEntityScore,
} from "@/lib/nc-api";

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function GET(_request: Request, { params }: RouteParams) {
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

    // Fetch articles and milestones in parallel
    const [articlesRes, milestones] = await Promise.all([
      getEntityArticles(entityData.id, { page_size: 50 }),
      getEntityMilestones(entityData.id).catch(() => []),
    ]);

    const politician = entityToPolitician(entityData, {
      entity_id: entityData.id,
      score: entityData.score,
      max_severity: entityData.max_severity,
      article_count: entityData.article_count,
    } as NCEntityScore);

    // Enrich milestoneCount with real data
    politician.milestoneCount = milestones.length;

    const articles = articlesRes.items.map(ncArticleToArticle);

    return NextResponse.json({
      politician,
      articles,
      milestones,
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
