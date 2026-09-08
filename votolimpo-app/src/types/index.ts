// Core types for Voto Limpo

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Politician {
  id: string;
  slug: string;
  name: string;
  party: string;
  partyColor: string;
  uf: string;
  role: string;
  photoUrl?: string;
  bio?: string;
  score: number; // 0-100 transparency score
  articleCount: number;
  maxSeverity: Severity;
  milestoneCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Article {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: NewsSource;
  publishedAt: string;
  severity: Severity;
  truthScore: number; // 0-1
  politicianIds: string[];
  tags: string[];
}

export interface NewsSource {
  id: string;
  name: string;
  url: string;
  logoUrl?: string;
  reliability: number; // 0-1
}

export interface Entity {
  id: string;
  slug: string;
  name: string;
  type: "company" | "organization" | "government" | "ngo" | "media";
  description?: string;
  cnpj?: string;
}

export interface Relationship {
  id: string;
  politicianId: string;
  entityId: string;
  type:
    | "donation"
    | "contract"
    | "board_member"
    | "investigation"
    | "business_partner"
    | "family";
  description: string;
  value?: number; // in BRL
  startDate?: string;
  endDate?: string;
  sources: string[];
}

export interface LegalMilestone {
  id: string;
  politicianId: string;
  title: string;
  description: string;
  type:
    | "indictment"
    | "conviction"
    | "acquittal"
    | "investigation"
    | "appeal"
    | "settlement"
    | "impeachment"
    | "election";
  date: string;
  court?: string;
  processNumber?: string;
  severity: Severity;
}

export interface TimelineItem {
  id: string;
  type: "article" | "milestone";
  date: string;
  title: string;
  description: string;
  severity: Severity;
  data: Article | LegalMilestone;
}

export interface GraphNode {
  id: string;
  type: "politician" | "entity";
  label: string;
  slug?: string;
  party?: string;
  partyColor?: string;
  score?: number;
  entityType?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: Relationship["type"];
  value?: number;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface Stats {
  totalPoliticians: number;
  totalArticles: number;
  totalEntities: number;
  totalRelationships: number;
  avgScore: number;
  criticalCount: number;
}

export interface SearchResult {
  politicians: Politician[];
  articles: Article[];
  total: number;
}

export type SortField =
  | "name"
  | "score"
  | "articleCount"
  | "maxSeverity"
  | "party"
  | "uf";
export type SortOrder = "asc" | "desc";

export interface RankingFilters {
  party?: string;
  uf?: string;
  minScore?: number;
  maxScore?: number;
  page?: number;
  pageSize?: number;
  sortBy?: SortField;
  sortOrder?: SortOrder;
}
