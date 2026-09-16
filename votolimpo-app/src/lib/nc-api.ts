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
  source_name: string | null;
  language: string | null;
  sentiment: string | null;
  sentiment_score: number | null;
  processing_status: string;
  word_count: number | null;
  created_at: string;
  updated_at: string;
  entities_linked: Record<string, unknown>[] | null;
  // PE-derived fields (populated by backend from processing_output)
  severity: string | null;
  is_political: boolean | null;
  score: number | null; // veracity 0-10 scale
  score_breakdown: Record<string, number> | null;
  pe_keywords: string[] | null;
  politicians: string[] | null;
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

export interface NCEntityScore {
  entity_id: number;
  score: number | null;      // 0-100, null = no processed articles
  max_severity: string;      // critical|high|medium|low|info
  article_count: number;
}

export interface NCVotoLimpoStats {
  avg_score: number | null;  // 0-100, null = no processed articles
  critical_count: number;
  entities_with_articles: number;
}

/** Entity enriched with score data (returned by by-slug endpoint) */
export interface NCEntityWithScore extends NCEntity {
  article_count: number;
  score: number | null;
  max_severity: string;
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

/** Count entities matching filters (mirrors listEntities params) */
export async function countEntities(params?: {
  type?: string;
  search?: string;
  active?: boolean;
}): Promise<number> {
  const res = await ncFetch<{ count: number }>({
    path: "/entities/count",
    params: params as Record<string, string | number | boolean | undefined>,
    revalidate: 300,
  });
  return res.count;
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
  severity?: string;
  is_political?: boolean;
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

/** Get aggregated score data for a single entity */
export async function getEntityScore(entityId: number): Promise<NCEntityScore> {
  return ncFetch<NCEntityScore>({
    path: `/entities/${entityId}/score`,
    revalidate: 120,
  });
}

/** Lookup entity by slug and get score data in one request */
export async function getEntityBySlug(slug: string): Promise<NCEntityWithScore> {
  return ncFetch<NCEntityWithScore>({
    path: `/entities/by-slug/${slug}`,
    revalidate: 120,
  });
}

/** Get VotoLimpo aggregated stats (avgScore, criticalCount) */
export async function getVotoLimpoStats(): Promise<NCVotoLimpoStats> {
  return ncFetch<NCVotoLimpoStats>({
    path: "/stats/votolimpo",
    revalidate: 120,
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
  scoreData?: NCEntityScore | null
): Politician {
  const meta = parseMetadata(entity.metadata_json);
  const photoUrl = (meta.foto_url as string) || undefined;

  // Score real do backend (0-100) ou 0 se null (sem artigos processados)
  const score = scoreData?.score ?? (entity as NCEntityWithScore).score ?? null;
  const articleCount =
    scoreData?.article_count ??
    (entity as NCEntityWithScore).article_count ??
    0;
  const maxSeverity = scoreData?.max_severity
    ? mapSeverity(scoreData.max_severity)
    : mapSeverity((entity as NCEntityWithScore).max_severity ?? "info");

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
    score: score ?? 0,  // 0 = sem dados suficientes (não 50)
    articleCount,
    maxSeverity,
    milestoneCount: 0,  // mantido até frente de Milestones
    createdAt: entity.created_at,
    updatedAt: entity.updated_at,
  };
}

/** Map PE severity string to frontend Severity type */
function mapSeverity(peSeverity: string | null): Severity {
  if (peSeverity && ["critical", "high", "medium", "low"].includes(peSeverity)) {
    return peSeverity as Severity;
  }
  return "info";
}

// Static reliability map per source domain
const SOURCE_RELIABILITY: Record<string, number> = {
  "g1.globo.com": 0.9,
  "globo.com": 0.9,
  "folha.uol.com.br": 0.9,
  "estadao.com.br": 0.9,
  "uol.com.br": 0.85,
  "bbc.com": 0.95,
  "bbc.co.uk": 0.95,
  "reuters.com": 0.95,
  "cnn.com": 0.85,
  "r7.com": 0.75,
  "terra.com.br": 0.75,
  "metropoles.com": 0.8,
  "poder360.com.br": 0.85,
  "congressoemfoco.uol.com.br": 0.85,
  "agenciabrasil.ebc.com.br": 0.85,
  "senado.leg.br": 0.9,
  "camara.leg.br": 0.9,
  "tse.jus.br": 0.95,
  "veja.abril.com.br": 0.8,
  "cartacapital.com.br": 0.75,
  "oantagonista.com": 0.65,
};

/** Return reliability score for a domain (0-1) */
export function getSourceReliability(domain: string | null): number {
  if (!domain) return 0.5;
  const clean = domain.replace(/^www\./, "").toLowerCase();
  return SOURCE_RELIABILITY[clean] ?? 0.6; // default 0.6 for unknown domains
}

/** Convert NC article to frontend Article type */
export function ncArticleToArticle(ncArt: NCArticle): Article {
  // Use PE-calculated severity when available, fallback to sentiment-based inference
  const severity: Severity = ncArt.severity
    ? mapSeverity(ncArt.severity)
    : ncArt.sentiment_score !== null
      ? ncArt.sentiment_score < 0.2 ? "critical"
        : ncArt.sentiment_score < 0.35 ? "high"
        : ncArt.sentiment_score < 0.5 ? "medium"
        : ncArt.sentiment_score < 0.65 ? "low"
        : "info"
      : "info";

  // Use PE veracity score (0-10) converted to 0-1, with float precision fix
  // score field uses 0-10 scale from PE
  const truthScore = ncArt.score !== null
    ? Math.round(ncArt.score * 10) / 100
    : ncArt.sentiment_score ?? 0.5;

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
      name: ncArt.source_name || formatSourceDomain(ncArt.source_domain),
      url: ncArt.source_domain ? `https://${ncArt.source_domain}` : "",
      reliability: getSourceReliability(ncArt.source_domain),
    },
    publishedAt: ncArt.published_at || ncArt.created_at,
    severity,
    truthScore,
    isPolitical: ncArt.is_political ?? undefined,
    tags: ncArt.pe_keywords ?? [],
    politicianIds: ncArt.politicians ?? [],
    scoreBreakdown: ncArt.score_breakdown ?? undefined,
    processingStatus: ncArt.processing_status,
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

/** Build Stats object from NC global stats and VotoLimpo stats */
export function ncStatsToStats(
  ncStats: NCStats,
  vlStats?: NCVotoLimpoStats | null
): Stats {
  return {
    totalPoliticians: ncStats.database.total_entities,
    totalArticles: ncStats.database.total_articles,
    totalEntities: ncStats.database.total_entities,
    totalRelationships: ncStats.database.total_sources,
    avgScore: vlStats?.avg_score ?? 0,
    criticalCount: vlStats?.critical_count ?? 0,
  };
}
