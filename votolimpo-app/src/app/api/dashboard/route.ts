import { NextResponse } from "next/server";
import {
  listEntities,
  countEntities,
  listArticles,
  getScoreDistribution,
  entityToPolitician,
  ncArticleToArticle,
  type NCEntityWithScore,
} from "@/lib/nc-api";
import type { Politician, Article } from "@/types";

interface DashboardData {
  top: Politician[];
  total: number;
  distribution: { label: string; min: number; max: number; count: number; color: string }[];
  articles: Article[];
  cargo: string;
  uf: string | null;
}

const SCORE_RANGES = [
  { label: "Excelente", min: 80, max: 100, color: "#34D399" },
  { label: "Bom", min: 60, max: 79, color: "#6EE7B7" },
  { label: "Regular", min: 40, max: 59, color: "#FBBF24" },
  { label: "Preocupante", min: 20, max: 39, color: "#F97316" },
  { label: "Crítico", min: 0, max: 19, color: "#EF4444" },
];

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const cargo = searchParams.get("cargo") || "";
    const uf = searchParams.get("uf") || undefined;

    if (!cargo) {
      return NextResponse.json({ error: "cargo is required" }, { status: 400 });
    }

    // Fetch top candidates, total count, score distribution, and articles in parallel
    const [topEntities, total, distBands, articlesRes] = await Promise.all([
      listEntities({
        type: "candidate",
        active: true,
        limit: 20,
        cargo,
        state: uf,
        order_by: "score",
        order_dir: "desc",
      }),
      countEntities({
        type: "candidate",
        active: true,
        cargo,
        state: uf,
      }),
      getScoreDistribution({ cargo, state: uf }).catch(() => null),
      listArticles({ status: "processed", page_size: 6 }),
    ]);

    // Map to Politician
    const top: Politician[] = topEntities.map((e) => {
      const enriched: NCEntityWithScore = {
        ...e,
        score: (e as NCEntityWithScore).score ?? null,
        max_severity: (e as NCEntityWithScore).max_severity ?? "info",
        article_count: (e as NCEntityWithScore).article_count ?? 0,
      };
      return entityToPolitician(enriched, {
        entity_id: enriched.id,
        score: enriched.score,
        max_severity: enriched.max_severity,
        article_count: enriched.article_count,
      });
    });

    // Use real score distribution from backend when available, fallback to top-20 approximation
    const distribution = distBands
      ? SCORE_RANGES.map((range) => {
          // Match by overlapping min/max (NC uses 0-20/21-40/..., frontend uses 0-19/20-39/...)
          const band = distBands.find(
            (b) => Math.abs(b.min - range.min) <= 1 && Math.abs(b.max - range.max) <= 1,
          );
          return { ...range, count: band?.count ?? 0 };
        })
      : SCORE_RANGES.map((range) => ({
          ...range,
          count: top.filter(
            (p) => p.score !== null && p.score >= range.min && p.score <= range.max,
          ).length,
        }));

    const articles = articlesRes.items.map(ncArticleToArticle);

    const data: DashboardData = {
      top,
      total,
      distribution,
      articles,
      cargo,
      uf: uf || null,
    };

    const response = NextResponse.json(data);
    response.headers.set(
      "Cache-Control",
      "public, s-maxage=60, stale-while-revalidate=300",
    );
    return response;
  } catch (error) {
    console.error("[api/dashboard] NC API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch dashboard data" },
      { status: 502 },
    );
  }
}
