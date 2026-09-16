"use client";

import { useState } from "react";

/* ─── Types ────────────────────────────────────────────────────────────────── */

interface StepData {
  number: number;
  title: string;
  subtitle: string;
  description: string;
  details: string[];
  outputs: string[];
  color: string;
  iconPath: string;
}

interface MetricData {
  label: string;
  description: string;
  values: string[];
  color: string;
  iconPath: string;
}

interface FaqData {
  question: string;
  answer: string;
}

/* ─── Icon helper (inline SVG) ─────────────────────────────────────────────── */

function Icon({ path, className = "" }: { path: string; className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

/* ─── Chevron icons ────────────────────────────────────────────────────────── */

const ChevronDown = () => (
  <svg className="h-4 w-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);

const ChevronUp = () => (
  <svg className="h-4 w-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
  </svg>
);

/* ─── SVG icon paths ───────────────────────────────────────────────────────── */

const ICONS = {
  globe: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
  brain: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  layers: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
  chart: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  check: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  arrowRight: "M13 7l5 5m0 0l-5 5m5-5H6",
  arrowDown: "M19 14l-7 7m0 0l-7-7m7 7V3",
  zap: "M13 10V3L4 14h7v7l9-11h-7z",
  shield: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  refresh: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  alert: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
  trending: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
  users: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
  search: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  newspaper: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z",
  clock: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  filter: "M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z",
  document: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  database: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4",
};

/* ─── Pipeline Step Component ──────────────────────────────────────────────── */

function PipelineStep({ step }: { step: StepData }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`w-full text-left rounded-2xl border border-surface-300 bg-surface p-6 hover:border-accent/30 transition-all duration-200`}
      >
        <div className="flex items-start gap-4">
          <div className={`flex items-center justify-center w-12 h-12 rounded-xl ${step.color} shrink-0`}>
            <Icon path={step.iconPath} className="text-current" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs font-mono text-muted">ETAPA {step.number}</span>
              <span className="text-xs text-surface-300">{step.subtitle}</span>
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">{step.title}</h3>
            <p className="text-sm text-muted leading-relaxed">{step.description}</p>
          </div>
          <div className="shrink-0 mt-1">{open ? <ChevronUp /> : <ChevronDown />}</div>
        </div>

        {open && (
          <div className="mt-5 pt-5 border-t border-surface-300">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Como funciona</h4>
                <ul className="space-y-2.5">
                  {step.details.map((d, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-foreground/80">
                      <Icon path={ICONS.check} className="text-accent-400 mt-0.5 shrink-0 h-4 w-4" />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">O que gera</h4>
                <ul className="space-y-2.5">
                  {step.outputs.map((o, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-foreground/80">
                      <Icon path={ICONS.arrowRight} className="text-blue-400 mt-0.5 shrink-0 h-4 w-4" />
                      <span>{o}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </button>
    </div>
  );
}

/* ─── Step connector ───────────────────────────────────────────────────────── */

function StepConnector() {
  return (
    <div className="flex justify-center py-2">
      <div className="flex flex-col items-center">
        <div className="w-px h-5 bg-gradient-to-b from-surface-300 to-accent/30" />
        <Icon path={ICONS.arrowDown} className="text-accent/40 h-4 w-4" />
      </div>
    </div>
  );
}

/* ─── Metric Card ──────────────────────────────────────────────────────────── */

function MetricCard({ metric }: { metric: MetricData }) {
  return (
    <div className="rounded-2xl border border-surface-300 bg-surface p-5 hover:border-accent/20 transition-colors">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-xl ${metric.color}`}>
          <Icon path={metric.iconPath} className="text-current h-4 w-4" />
        </div>
        <h4 className="font-semibold text-foreground text-sm">{metric.label}</h4>
      </div>
      <p className="text-sm text-muted mb-4 leading-relaxed">{metric.description}</p>
      <div className="flex flex-wrap gap-2">
        {metric.values.map((v, i) => (
          <span key={i} className="px-2.5 py-1 rounded-full text-xs font-medium bg-surface-200 text-foreground/70 border border-surface-300">
            {v}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ─── FAQ Accordion ────────────────────────────────────────────────────────── */

function FaqAccordion({ items }: { items: FaqData[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      {items.map((item, i) => (
        <div key={i} className="rounded-2xl border border-surface-300 bg-surface overflow-hidden">
          <button
            onClick={() => setOpenIdx(openIdx === i ? null : i)}
            className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-surface-100 transition-colors"
          >
            <span className="text-sm font-medium text-foreground pr-4">{item.question}</span>
            {openIdx === i ? <ChevronUp /> : <ChevronDown />}
          </button>
          {openIdx === i && (
            <div className="px-5 pb-5">
              <p className="text-sm text-muted leading-relaxed">{item.answer}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ─── SVG Flowchart ────────────────────────────────────────────────────────── */

function Flowchart() {
  return (
    <div className="rounded-2xl border border-surface-300 bg-surface/50 p-4 sm:p-6 overflow-x-auto">
      <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-5">Fluxo Visual do Pipeline</h3>
      <svg viewBox="0 0 900 520" className="w-full min-w-[640px]" style={{ maxHeight: 520 }}>
        <defs>
          <marker id="ah" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#4B5563" />
          </marker>
          <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#10B981" stopOpacity="0.12" /><stop offset="100%" stopColor="#10B981" stopOpacity="0.03" /></linearGradient>
          <linearGradient id="g2" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.12" /><stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.03" /></linearGradient>
          <linearGradient id="g3" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#F59E0B" stopOpacity="0.12" /><stop offset="100%" stopColor="#F59E0B" stopOpacity="0.03" /></linearGradient>
          <linearGradient id="g4" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#3B82F6" stopOpacity="0.12" /><stop offset="100%" stopColor="#3B82F6" stopOpacity="0.03" /></linearGradient>
        </defs>

        {/* Row 1: Coleta */}
        <rect x="20" y="20" width="860" height="90" rx="14" fill="url(#g1)" stroke="#10B981" strokeWidth="1" strokeOpacity="0.25" />
        <text x="40" y="48" fill="#10B981" fontSize="11" fontWeight="600" fontFamily="ui-monospace, monospace">ETAPA 1 — COLETA DE NOTÍCIAS</text>
        <rect x="40" y="58" width="120" height="38" rx="10" fill="#141414" stroke="#2E2E2E" strokeWidth="1" />
        <text x="100" y="82" fill="#9CA3AF" fontSize="11" textAnchor="middle">Sites de Notícia</text>
        <rect x="180" y="58" width="120" height="38" rx="10" fill="#141414" stroke="#2E2E2E" strokeWidth="1" />
        <text x="240" y="82" fill="#9CA3AF" fontSize="11" textAnchor="middle">Google News</text>
        <rect x="320" y="58" width="100" height="38" rx="10" fill="#141414" stroke="#2E2E2E" strokeWidth="1" />
        <text x="370" y="82" fill="#9CA3AF" fontSize="11" textAnchor="middle">RSS Feeds</text>
        <rect x="450" y="58" width="140" height="38" rx="10" fill="#141414" stroke="#2E2E2E" strokeWidth="1" />
        <text x="520" y="82" fill="#9CA3AF" fontSize="11" textAnchor="middle">Crawler Inteligente</text>
        <rect x="620" y="58" width="120" height="38" rx="10" fill="#141414" stroke="#2E2E2E" strokeWidth="1" />
        <text x="680" y="82" fill="#9CA3AF" fontSize="11" textAnchor="middle">Deduplicação</text>
        <rect x="770" y="58" width="90" height="38" rx="10" fill="#064E3B" stroke="#10B981" strokeWidth="1" />
        <text x="815" y="82" fill="#34D399" fontSize="11" textAnchor="middle" fontWeight="600">Artigos</text>
        {/* Arrows */}
        <line x1="160" y1="77" x2="178" y2="77" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" />
        <line x1="300" y1="77" x2="318" y2="77" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" />
        <line x1="420" y1="77" x2="448" y2="77" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" />
        <line x1="590" y1="77" x2="618" y2="77" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" />
        <line x1="740" y1="77" x2="768" y2="77" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" />

        {/* Connector */}
        <line x1="450" y1="110" x2="450" y2="140" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" strokeDasharray="4 3" />

        {/* Row 2: Analise IA */}
        <rect x="20" y="145" width="860" height="120" rx="14" fill="url(#g2)" stroke="#8B5CF6" strokeWidth="1" strokeOpacity="0.25" />
        <text x="40" y="173" fill="#8B5CF6" fontSize="11" fontWeight="600" fontFamily="ui-monospace, monospace">ETAPA 2 — ANÁLISE POR INTELIGÊNCIA ARTIFICIAL</text>
        <rect x="40" y="185" width="150" height="60" rx="10" fill="#1E1B2E" stroke="#4C1D95" strokeWidth="1" />
        <text x="115" y="210" fill="#A78BFA" fontSize="11" textAnchor="middle" fontWeight="500">Classificação</text>
        <text x="115" y="227" fill="#7C3AED" fontSize="9" textAnchor="middle">Político / Não-político</text>
        <rect x="210" y="185" width="140" height="60" rx="10" fill="#1E1B2E" stroke="#4C1D95" strokeWidth="1" />
        <text x="280" y="210" fill="#A78BFA" fontSize="11" textAnchor="middle" fontWeight="500">Sentimento</text>
        <text x="280" y="227" fill="#7C3AED" fontSize="9" textAnchor="middle">Positivo / Negativo / Neutro</text>
        <rect x="370" y="185" width="140" height="60" rx="10" fill="#1E1B2E" stroke="#4C1D95" strokeWidth="1" />
        <text x="440" y="210" fill="#A78BFA" fontSize="11" textAnchor="middle" fontWeight="500">Gravidade</text>
        <text x="440" y="227" fill="#7C3AED" fontSize="9" textAnchor="middle">Baixa / Média / Alta / Crítica</text>
        <rect x="530" y="185" width="140" height="60" rx="10" fill="#1E1B2E" stroke="#4C1D95" strokeWidth="1" />
        <text x="600" y="210" fill="#A78BFA" fontSize="11" textAnchor="middle" fontWeight="500">Veracidade</text>
        <text x="600" y="227" fill="#7C3AED" fontSize="9" textAnchor="middle">Score 0 a 10</text>
        <rect x="690" y="185" width="170" height="60" rx="10" fill="#1E1B2E" stroke="#4C1D95" strokeWidth="1" />
        <text x="775" y="210" fill="#A78BFA" fontSize="11" textAnchor="middle" fontWeight="500">Entidades e Resumo</text>
        <text x="775" y="227" fill="#7C3AED" fontSize="9" textAnchor="middle">Politicos + Keywords + Resumo</text>

        {/* Connector */}
        <line x1="450" y1="265" x2="450" y2="295" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" strokeDasharray="4 3" />

        {/* Row 3: Enriquecimento */}
        <rect x="20" y="300" width="860" height="90" rx="14" fill="url(#g3)" stroke="#F59E0B" strokeWidth="1" strokeOpacity="0.25" />
        <text x="40" y="328" fill="#F59E0B" fontSize="11" fontWeight="600" fontFamily="ui-monospace, monospace">ETAPA 3 — ENRIQUECIMENTO E VINCULAÇÃO</text>
        <rect x="40" y="338" width="180" height="38" rx="10" fill="#1C1500" stroke="#854D0E" strokeWidth="1" />
        <text x="130" y="362" fill="#FBBF24" fontSize="11" textAnchor="middle">Vinculação a Candidatos</text>
        <rect x="240" y="338" width="160" height="38" rx="10" fill="#1C1500" stroke="#854D0E" strokeWidth="1" />
        <text x="320" y="362" fill="#FBBF24" fontSize="11" textAnchor="middle">Agrupamento (Clusters)</text>
        <rect x="420" y="338" width="180" height="38" rx="10" fill="#1C1500" stroke="#854D0E" strokeWidth="1" />
        <text x="510" y="362" fill="#FBBF24" fontSize="11" textAnchor="middle">Dados TSE (Partidos, UF)</text>
        <rect x="620" y="338" width="240" height="38" rx="10" fill="#1C1500" stroke="#854D0E" strokeWidth="1" />
        <text x="740" y="362" fill="#FBBF24" fontSize="11" textAnchor="middle">Índices e Estatísticas Agregadas</text>

        {/* Connector */}
        <line x1="450" y1="390" x2="450" y2="420" stroke="#4B5563" strokeWidth="1.5" markerEnd="url(#ah)" strokeDasharray="4 3" />

        {/* Row 4: Visualizacao */}
        <rect x="20" y="425" width="860" height="80" rx="14" fill="url(#g4)" stroke="#3B82F6" strokeWidth="1" strokeOpacity="0.25" />
        <text x="40" y="453" fill="#3B82F6" fontSize="11" fontWeight="600" fontFamily="ui-monospace, monospace">ETAPA 4 — VISUALIZAÇÃO NO VOTOLIMPO.COM.BR</text>
        <rect x="40" y="462" width="130" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="105" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Página Inicial</text>
        <rect x="190" y="462" width="130" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="255" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Ranking</text>
        <rect x="340" y="462" width="130" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="405" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Perfil do Político</text>
        <rect x="490" y="462" width="130" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="555" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Busca</text>
        <rect x="640" y="462" width="120" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="700" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Grafo</text>
        <rect x="780" y="462" width="80" height="32" rx="8" fill="#172554" stroke="#1E40AF" strokeWidth="1" />
        <text x="820" y="483" fill="#60A5FA" fontSize="11" textAnchor="middle">Gráficos</text>
      </svg>
    </div>
  );
}

/* ─── Data ─────────────────────────────────────────────────────────────────── */

const STEPS: StepData[] = [
  {
    number: 1,
    title: "Coleta Automática de Notícias",
    subtitle: "News Collector",
    color: "bg-accent/10 text-accent-400",
    iconPath: ICONS.globe,
    description:
      "O sistema varre automaticamente centenas de fontes de notícias na internet, buscando matérias sobre os candidatos e entidades monitoradas. A coleta pode ser agendada ou disparada manualmente.",
    details: [
      "Fontes configuradas por entidade: sites de notícias, Google News, feeds RSS",
      "Crawler inteligente extrai título, texto completo, autor e data de publicação",
      "Deduplicação automática impede que a mesma notícia entre duas vezes",
      "Controle de velocidade por domínio evita sobrecarregar os sites de origem",
      "Circuit breaker: se um site estiver fora do ar, o sistema para de tentar temporariamente e retoma quando volta",
    ],
    outputs: [
      "Artigos brutos com texto completo",
      "Metadados: domínio de origem, autor, data de publicação",
      "Hash único de URL para evitar duplicatas",
      "Registro do job de coleta (encontrados, novos, duplicados)",
    ],
  },
  {
    number: 2,
    title: "Análise por Inteligência Artificial",
    subtitle: "Processing Engine (PE)",
    color: "bg-purple-500/10 text-purple-400",
    iconPath: ICONS.brain,
    description:
      "Cada artigo coletado é enviado para o Motor de Processamento, que usa modelos de IA (LLM) para analisar o conteúdo em múltiplas dimensões. É aqui que os scores e classificações são gerados.",
    details: [
      "O artigo é enviado em lote para o PE via API segura com autenticação",
      "A IA lê o texto completo e gera análises simultâneas em múltiplas dimensões",
      "Sentimento: avalia se o tom da notícia é positivo, negativo ou neutro",
      "Gravidade: classifica o impacto potencial (baixa, média, alta, crítica)",
      "Veracidade: score de 0 a 10 indicando consistência e confiabilidade",
      "Classificação política: identifica se a notícia tem cunho político",
      "Extração de entidades: identifica quais políticos são mencionados no texto",
      "Resumo automático: gera um resumo conciso com os pontos principais",
    ],
    outputs: [
      "Sentimento (positivo / negativo / neutro)",
      "Gravidade (baixa / média / alta / crítica)",
      "Score de veracidade (0 a 10)",
      "Classificação política (sim / não)",
      "Lista de políticos mencionados",
      "Keywords extraídas automaticamente",
      "Resumo automático do artigo",
    ],
  },
  {
    number: 3,
    title: "Enriquecimento e Vinculação",
    subtitle: "Entity Matching + Clusters",
    color: "bg-yellow-500/10 text-yellow-400",
    iconPath: ICONS.layers,
    description:
      "Os artigos analisados são vinculados aos candidatos cadastrados no sistema e agrupados por assunto. Dados do TSE complementam as informações de cada entidade.",
    details: [
      "Entity Matcher: cruza nomes mencionados nos artigos com candidatos cadastrados",
      "Aliases: variantes de nome (apelidos, nomes parciais) também são reconhecidas",
      "Clusters: artigos sobre o mesmo assunto são agrupados automaticamente",
      "Dados do TSE são importados: partido, estado, cargo, número de urna, foto",
      "Estatísticas agregadas: total de menções por candidato, tendências ao longo do tempo",
    ],
    outputs: [
      "Artigos vinculados a entidades específicas (candidatos, partidos)",
      "Clusters temáticos — agrupamento por assunto",
      "Perfil enriquecido de cada candidato com dados eleitorais do TSE",
      "Contagem de menções e distribuições por entidade e período",
    ],
  },
  {
    number: 4,
    title: "Visualização no VotoLimpo.com.br",
    subtitle: "Frontend Público",
    color: "bg-blue-500/10 text-blue-400",
    iconPath: ICONS.chart,
    description:
      "Todas as informações são apresentadas aqui, neste site, de forma visual e acessível: ranking de políticos, perfis individuais, busca de artigos, grafo de conexões e gráficos interativos.",
    details: [
      "Página inicial: visão geral com destaques, notícias recentes e top políticos",
      "Ranking: classificação dos políticos por volume de notícias e indicadores",
      "Perfil do político: histórico completo de notícias, scores e dados eleitorais",
      "Busca: filtragem por texto, sentimento, gravidade, entidade e período",
      "Grafo: visualização interativa de conexões entre políticos e temas",
      "Tudo atualizado automaticamente conforme novas coletas são processadas",
    ],
    outputs: [
      "Painel público em tempo real no votolimpo.com.br",
      "Perfis individuais por candidato com gráficos e histórico",
      "Busca e filtragem acessíveis a qualquer cidadão",
    ],
  },
];

const METRICS: MetricData[] = [
  {
    label: "Sentimento",
    color: "bg-purple-500/10 text-purple-400",
    iconPath: ICONS.trending,
    description: "A IA avalia o tom geral do artigo em relação ao assunto e às pessoas mencionadas. Não é sobre \"bom ou ruim\", mas sobre a carga emocional do texto.",
    values: ["Positivo", "Negativo", "Neutro"],
  },
  {
    label: "Gravidade (Severity)",
    color: "bg-yellow-500/10 text-yellow-400",
    iconPath: ICONS.alert,
    description: "Indica o potencial impacto da notícia. Uma denúncia de corrupção tende a ser \"crítica\", enquanto uma agenda de campanha é \"baixa\".",
    values: ["Baixa", "Média", "Alta", "Crítica"],
  },
  {
    label: "Veracidade (Score 0-10)",
    color: "bg-blue-500/10 text-blue-400",
    iconPath: ICONS.shield,
    description: "Score de 0 a 10 que avalia a consistência, fontes citadas e indicadores de confiabilidade do artigo. Quanto maior, mais confiável parece o conteúdo.",
    values: ["0-3: Baixa confiança", "4-6: Moderada", "7-10: Alta confiança"],
  },
  {
    label: "Classificação Política",
    color: "bg-accent/10 text-accent-400",
    iconPath: ICONS.users,
    description: "A IA identifica se o artigo tem conteúdo político (menciona candidatos, partidos, eleições) ou se é uma notícia sem cunho político.",
    values: ["Político", "Não-político"],
  },
  {
    label: "Keywords Extraídas",
    color: "bg-rose-500/10 text-rose-400",
    iconPath: ICONS.search,
    description: "Palavras-chave automaticamente identificadas pela IA que representam os temas centrais do artigo. Usadas para busca e agrupamento.",
    values: ["Temas", "Pessoas", "Locais", "Organizações"],
  },
  {
    label: "Resumo Automático",
    color: "bg-cyan-500/10 text-cyan-400",
    iconPath: ICONS.newspaper,
    description: "A IA gera um resumo conciso de cada artigo, destacando os pontos principais. Útil para triagem rápida sem precisar ler o texto completo.",
    values: ["1-3 parágrafos", "Pontos principais", "Contexto"],
  },
];

const FAQ: FaqData[] = [
  {
    question: "De onde vêm as notícias?",
    answer: "As notícias são coletadas de fontes configuradas no sistema: portais de notícias, Google News e feeds RSS. Cada entidade monitorada (candidato, partido) tem suas próprias fontes. O crawler acessa essas páginas, extrai o conteúdo e salva no banco de dados automaticamente.",
  },
  {
    question: "Como o score de veracidade é calculado?",
    answer: "O score de veracidade (0 a 10) é gerado pela IA analisando múltiplos sinais: presença de fontes citadas, consistência factual, linguagem utilizada, presença de dados verificáveis, entre outros. Cada sinal contribui para o score final. Não é uma verificação de fatos definitiva, mas um indicador de confiabilidade baseado em padrões textuais.",
  },
  {
    question: "Qual a diferença entre sentimento e gravidade?",
    answer: "Sentimento mede o tom emocional do texto (positivo, negativo, neutro) — como a notícia \"soa\". Gravidade mede o potencial impacto da informação (baixa a crítica) — quão séria é a notícia. Uma notícia pode ter sentimento negativo mas gravidade baixa (ex: crítica leve), ou sentimento neutro mas gravidade crítica (ex: relatório objetivo sobre corrupção).",
  },
  {
    question: "O que são os Clusters?",
    answer: "Clusters são agrupamentos automáticos de artigos que tratam do mesmo assunto. Se 10 portais noticiaram o mesmo evento, esses artigos serão agrupados em um único cluster, facilitando a análise comparativa e evitando duplicidade na leitura.",
  },
  {
    question: "Com que frequência as notícias são coletadas?",
    answer: "A frequência é configurável por agendamento. Pode ser a cada hora, diariamente, ou em qualquer intervalo definido. Coletas manuais também podem ser disparadas a qualquer momento pela equipe de operação.",
  },
  {
    question: "O que acontece se um site de notícias estiver fora do ar?",
    answer: "O sistema possui um Circuit Breaker por domínio: se muitas requisições falharem seguidas, ele para de tentar acessar aquele site por um período configurável. Quando o site volta ao normal, o sistema retoma automaticamente. Isso protege tanto o nosso sistema quanto o site de destino.",
  },
  {
    question: "Os dados são confiáveis?",
    answer: "Os dados de notícias são públicos e verificáveis. Os scores gerados pela IA são indicadores automáticos — eles não substituem a leitura crítica do conteúdo, mas servem como ferramenta de triagem e classificação. Dados eleitorais vêm diretamente do TSE (Tribunal Superior Eleitoral).",
  },
];

/* ─── Page ─────────────────────────────────────────────────────────────────── */

export default function ComoFuncionaPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8 space-y-14">
      {/* Hero */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold">
          <Icon path={ICONS.zap} className="h-3.5 w-3.5" />
          Pipeline Completo
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground tracking-tight">
          Como Funciona o <span className="text-accent">VotoLimpo</span>
        </h1>
        <p className="text-muted max-w-2xl mx-auto leading-relaxed">
          Da coleta automática de notícias até a geração de scores e gráficos — entenda cada
          etapa do pipeline e como cada métrica é calculada.
        </p>
      </div>

      {/* Flowchart */}
      <Flowchart />

      {/* Pipeline Steps */}
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
          <Icon path={ICONS.database} className="text-muted h-5 w-5" />
          Pipeline Passo a Passo
        </h2>
        <p className="text-sm text-muted mb-6">
          Clique em cada etapa para ver os detalhes de como funciona e o que é gerado.
        </p>
        <div>
          {STEPS.map((step, i) => (
            <div key={step.number}>
              <PipelineStep step={step} />
              {i < STEPS.length - 1 && <StepConnector />}
            </div>
          ))}
        </div>
      </section>

      {/* Metrics */}
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-2 flex items-center gap-2">
          <Icon path={ICONS.chart} className="text-muted h-5 w-5" />
          Métricas e Scores Explicados
        </h2>
        <p className="text-sm text-muted mb-6">
          Cada artigo processado recebe as seguintes métricas, todas geradas pela Inteligência Artificial:
        </p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {METRICS.map((m) => (
            <MetricCard key={m.label} metric={m} />
          ))}
        </div>
      </section>

      {/* Resilience */}
      <section className="rounded-2xl border border-surface-300 bg-surface/50 p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Icon path={ICONS.refresh} className="text-muted h-5 w-5" />
          Resiliência do Sistema
        </h2>
        <p className="text-sm text-muted mb-5">
          O sistema foi construído para funcionar de forma autônoma e se recuperar de falhas automaticamente:
        </p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: ICONS.refresh, title: "Reenvio Automático", desc: "Se a IA não responder, o artigo é reenviado automaticamente após alguns minutos" },
            { icon: ICONS.shield, title: "Circuit Breaker", desc: "Sites com problemas são pausados temporariamente para não sobrecarregar o sistema" },
            { icon: ICONS.clock, title: "Polling de Fallback", desc: "Se o callback não chegar, o sistema busca os resultados ativamente no serviço de IA" },
            { icon: ICONS.filter, title: "Deduplicação", desc: "Mesma notícia de fontes diferentes é detectada e não entra duas vezes no sistema" },
          ].map((f) => (
            <div key={f.title} className="p-4 rounded-xl bg-surface border border-surface-300">
              <div className="flex items-center gap-2 mb-2 text-foreground/80">
                <Icon path={f.icon} className="h-4 w-4" />
                <span className="text-sm font-medium">{f.title}</span>
              </div>
              <p className="text-xs text-muted leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
          <Icon path={ICONS.document} className="text-muted h-5 w-5" />
          Perguntas Frequentes
        </h2>
        <FaqAccordion items={FAQ} />
      </section>
    </div>
  );
}
