/**
 * News Collector API client — server-side only.
 *
 * Used by Next.js API routes (BFF layer) to proxy requests
 * to the NC backend without exposing the internal URL or token.
 */

const NC_API_URL =
  process.env.NC_API_URL || "https://api.news-collector.digital-ai.tech";
const NC_API_TOKEN = process.env.NC_API_TOKEN || "";

// ---------------------------------------------------------------------------
// Generic fetcher
// ---------------------------------------------------------------------------

interface FetchOptions {
  path: string;
  params?: Record<string, string | number | boolean | undefined>;
  revalidate?: number; // seconds
}

async function ncFetch<T>(opts: FetchOptions): Promise<T> {
  const url = new URL(opts.path, NC_API_URL);

  if (opts.params) {
    for (const [key, value] of Object.entries(opts.params)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000); // 15s timeout

  try {
    const res = await fetch(url.toString(), {
      headers: {
        Authorization: `Bearer ${NC_API_TOKEN}`,
        Accept: "application/json",
      },
      next: { revalidate: opts.revalidate ?? 60 },
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        `NC API error ${res.status} on ${opts.path}: ${text.slice(0, 200)}`
      );
    }

    return res.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`NC API timeout on ${opts.path} (15s exceeded)`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// NC API response types (mirrors the actual API schema)
// ---------------------------------------------------------------------------

export interface NCEntity {
  id: number;
  name: string;
  slug: string;
  type: string; // "candidate" | "topic" | ...
  cpf_hash: string | null;
  party: string | null;
  state: string | null;
  role: string | null;
  active: boolean;
  metadata_json: string | null;
  created_at: string;
  updated_at: string;
}

export interface NCArticle {
  id: number;
  job_id: number | null;
  url: string;
  url_hash: string;
  title: string | null;
  content: string | null;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  source_domain: string | null;
  language: string | null;
  sentiment: string | null;
  sentiment_score: number | null;
  processing_status: string;
  word_count: number | null;
  created_at: string;
  updated_at: string;
  entities_linked: Record<string, unknown>[] | null;
}

export interface NCPaginatedArticles {
  items: NCArticle[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface NCStats {
  database: {
    total_entities: number;
    total_sources: number;
    total_articles: number;
    total_jobs: number;
    articles_last_24h: number;
    jobs_last_24h: number;
    dedup_rate: number;
  };
  scheduler_running: boolean;
  collected_at: string;
}

export interface NCEntityStats {
  entity_id: number;
  entity_name: string;
  entity_slug: string;
  sources: { total: number; active: number };
  jobs: { total: number; last_24h: number };
  articles: { total: number; last_24h: number; last_7d: number };
  dedup_rate: number;
  collected_at: string;
}

export interface NCDistribution {
  sentiment_distribution: { label: string; count: number }[];
  processing_status_distribution: { label: string; count: number }[];
  source_domain_top10: { label: string; count: number }[];
  entity_type_distribution: { label: string; count: number }[];
}

export interface NCTimeseriesPoint {
  date: string;
  articles_collected: number;
  articles_new: number;
  articles_duplicate: number;
  articles_processed: number;
}

export interface NCTopEntity {
  entity_id: number;
  entity_name: string;
  entity_slug: string;
  article_count: number;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

/** List entities with optional filters */
export async function listEntities(params?: {
  type?: string;
  search?: string;
  active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<NCEntity[]> {
  return ncFetch<NCEntity[]>({
    path: "/entities/",
    params: params as Record<string, string | number | boolean | undefined>,
    revalidate: 300, // 5 min cache
  });
}

/** Get a single entity by ID */
export async function getEntity(id: number): Promise<NCEntity> {
  return ncFetch<NCEntity>({ path: `/entities/${id}`, revalidate: 300 });
}

/** Get articles for a specific entity */
export async function getEntityArticles(
  entityId: number,
  params?: {
    page?: number;
    page_size?: number;
    since?: string;
    until?: string;
    sentiment?: string;
  }
): Promise<NCPaginatedArticles> {
  return ncFetch<NCPaginatedArticles>({
    path: `/entities/${entityId}/articles`,
    params: params as Record<string, string | number | boolean | undefined>,
    revalidate: 120,
  });
}

/** Get entity-specific stats */
export async function getEntityStats(
  entityId: number
): Promise<NCEntityStats> {
  return ncFetch<NCEntityStats>({
    path: `/stats/entity/${entityId}`,
    revalidate: 120,
  });
}

/** List articles with filters */
export async function listArticles(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  entity_id?: number;
}): Promise<NCPaginatedArticles> {
  return ncFetch<NCPaginatedArticles>({
    path: "/articles/",
    params: params as Record<string, string | number | boolean | undefined>,
    revalidate: 60,
  });
}

/** Get a single article */
export async function getArticle(id: number): Promise<NCArticle> {
  return ncFetch<NCArticle>({ path: `/articles/${id}`, revalidate: 120 });
}

/** Get global stats */
export async function getGlobalStats(): Promise<NCStats> {
  return ncFetch<NCStats>({ path: "/stats/", revalidate: 120 });
}

/** Get distribution stats */
export async function getDistribution(): Promise<NCDistribution> {
  return ncFetch<NCDistribution>({
    path: "/stats/distribution",
    revalidate: 300,
  });
}

/** Get timeseries data */
export async function getTimeseries(
  period: "day" | "week" | "month" = "day"
): Promise<{ period: string; points: NCTimeseriesPoint[] }> {
  return ncFetch({
    path: "/stats/timeseries",
    params: { period },
    revalidate: 300,
  });
}

/** Get top entities by article count */
export async function getTopEntities(
  limit = 20,
  since?: string
): Promise<{ items: NCTopEntity[]; total: number }> {
  return ncFetch({
    path: "/stats/top-entities",
    params: { limit, since },
    revalidate: 300,
  });
}

// ---------------------------------------------------------------------------
// Transformation helpers — NC data -> frontend types
// ---------------------------------------------------------------------------

import type { Politician, Article, Severity, Stats } from "@/types";

/** Parse the metadata_json string from an NC entity */
function parseMetadata(
  raw: string | null
): Record<string, unknown> {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

/** Map party name to a representative color */
function partyColor(party: string | null): string {
  const colors: Record<string, string> = {
    PT: "#CC0000",
    PL: "#002776",
    MDB: "#00A859",
    PSDB: "#003DA5",
    PSB: "#FF6600",
    PP: "#1e3a8a",
    PDT: "#009B3A",
    PODE: "#D4AF37",
    "UNIAO": "#FFD700",
    "UNIAO BRASIL": "#FFD700",
    "UNIÃO": "#FFD700",
    "UNIÃO BRASIL": "#FFD700",
    NOVO: "#FF6600",
    PSD: "#0066CC",
    PSOL: "#FFCC00",
    REDE: "#00B4D8",
    AVANTE: "#FF4500",
    PCdoB: "#FF0000",
    REPUBLICANOS: "#1B3A73",
    SOLIDARIEDADE: "#FF8C00",
    CIDADANIA: "#FF69B4",
    PV: "#00A550",
  };
  if (!party) return "#6B7280";
  const upper = party.toUpperCase();
  return colors[upper] || "#6B7280";
}

/** Convert NC entity to frontend Politician type */
export function entityToPolitician(
  entity: NCEntity,
  articleCount = 0
): Politician {
  const meta = parseMetadata(entity.metadata_json);
  const photoUrl =
    (meta.foto_url as string) || undefined;

  return {
    id: String(entity.id),
    slug: entity.slug,
    name: entity.name,
    party: entity.party || "Sem Partido",
    partyColor: partyColor(entity.party),
    uf: entity.state || (meta.uf_candidatura as string) || "BR",
    role: entity.role || "Candidato",
    photoUrl,
    bio: undefined,
    score: 50, // placeholder — score will come from processing_output later
    articleCount,
    maxSeverity: "info" as Severity,
    milestoneCount: 0,
    createdAt: entity.created_at,
    updatedAt: entity.updated_at,
  };
}

/** Convert NC article to frontend Article type */
export function ncArticleToArticle(ncArt: NCArticle): Article {
  // Determine severity from sentiment_score
  let severity: Severity = "info";
  if (ncArt.sentiment_score !== null) {
    if (ncArt.sentiment_score < 0.2) severity = "critical";
    else if (ncArt.sentiment_score < 0.35) severity = "high";
    else if (ncArt.sentiment_score < 0.5) severity = "medium";
    else if (ncArt.sentiment_score < 0.65) severity = "low";
  }

  // Extract clean title (strip HTML from content if title missing)
  let title = ncArt.title || "";
  if (!title && ncArt.content) {
    const match = ncArt.content.match(/>([^<]+)</);
    if (match) title = match[1];
  }

  return {
    id: String(ncArt.id),
    title,
    summary: ncArt.summary || title,
    url: ncArt.url,
    source: {
      id: ncArt.source_domain || "unknown",
      name: formatSourceDomain(ncArt.source_domain),
      url: ncArt.source_domain
        ? `https://${ncArt.source_domain}`
        : "",
      reliability: 0.8,
    },
    publishedAt: ncArt.published_at || ncArt.created_at,
    severity,
    truthScore: ncArt.sentiment_score ?? 0.5,
    politicianIds: [],
    tags: [],
  };
}

function formatSourceDomain(domain: string | null): string {
  if (!domain) return "Fonte desconhecida";
  return domain
    .replace(/^www\./, "")
    .replace(/\.com\.br$/, "")
    .replace(/\.com$/, "")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Build Stats object from NC global stats */
export function ncStatsToStats(ncStats: NCStats): Stats {
  return {
    totalPoliticians: ncStats.database.total_entities,
    totalArticles: ncStats.database.total_articles,
    totalEntities: ncStats.database.total_entities,
    totalRelationships: ncStats.database.total_sources,
    avgScore: 50,
    criticalCount: 0,
  };
}
