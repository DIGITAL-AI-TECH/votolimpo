export const AREAS = [
  "Alto Valor",
  "Atendimento",
  "Autoatendimento",
  "BackOffice",
  "BB - Não Associada ao Bradesco",
  "Câmbio",
  "Cartões",
  "Cobrança",
  "Consórcio",
  "Conta Corrente",
  "Conta Salário",
  "Crédito",
  "Diversos",
  "Financiamento",
  "Investimentos",
  "Jurídico",
  "Ouvidoria",
  "Previdência",
  "Produtos e Serviços",
  "Renegociação",
  "SAC",
  "SAC Cartões",
  "Seguros",
  "Suporte Técnico",
  "Tesouraria",
  "Universidade Bradesco",
] as const;

export type Area = (typeof AREAS)[number];

export const PRIORITY_LEVELS = ["critical", "high", "medium", "low"] as const;
export type PriorityLevel = (typeof PRIORITY_LEVELS)[number];

export const CLASSIFICATIONS = ["TEXTUAL", "LINK_ONLY", "SHORT_TEXT"] as const;
export type Classification = (typeof CLASSIFICATIONS)[number];

export const REVIEW_ACTIONS = ["approved", "rejected", "revision_requested"] as const;
export type ReviewActionType = (typeof REVIEW_ACTIONS)[number];

export const PAGINATION = {
  DEFAULT_PAGE: 1,
  DEFAULT_PER_PAGE: 50,
  MAX_PER_PAGE: 100,
} as const;

export const PRIORITY_COLORS: Record<string, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#EAB308",
  low: "#22C55E",
};

export const AUTO_REFRESH_INTERVAL = 30_000; // 30 seconds
