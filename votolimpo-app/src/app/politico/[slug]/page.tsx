import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import {
  getEntityBySlug,
  getEntityArticles,
  getEntityMilestones,
  getEntityStats,
  entityToPolitician,
  ncArticleToArticle,
  ncMilestoneToLegalMilestone,
  type NCEntityScore,
} from "@/lib/nc-api";
import type { LegalMilestone } from "@/types";

import ScoreBadge from "@/components/ScoreBadge";
import SeverityBadge from "@/components/SeverityBadge";
import ShareButton from "@/components/ShareButton";
import Timeline from "@/components/Timeline";
import { buildTimelineItems } from "@/lib/timeline-utils";

export const revalidate = 120;

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const canonicalUrl = `https://votolimpo.com.br/politico/${slug}`;

  try {
    const entityData = await getEntityBySlug(slug);
    const politician = entityToPolitician(entityData, {
      entity_id: entityData.id,
      score: entityData.score,
      max_severity: entityData.max_severity,
      article_count: entityData.article_count,
    } as NCEntityScore);
    const title = politician.name;
    const description = `Perfil completo de ${politician.name} — ${politician.party} · ${politician.uf}. Consulte o histórico, vínculos e o índice de transparência no Voto Limpo.`;
    return {
      title,
      description,
      alternates: {
        canonical: canonicalUrl,
      },
      openGraph: {
        type: "profile",
        url: canonicalUrl,
        title: `${title} | Voto Limpo`,
        description,
        siteName: "Voto Limpo",
      },
      twitter: {
        card: "summary_large_image",
        title: `${title} | Voto Limpo`,
        description,
      },
    };
  } catch {
    return {
      title: "Erro ao carregar perfil",
      robots: { index: false, follow: false },
    };
  }
}

export default async function PoliticoPage({ params }: PageProps) {
  const { slug } = await params;

  let entityData;
  try {
    entityData = await getEntityBySlug(slug);
  } catch (error) {
    console.error("[PoliticoPage] NC API error:", error);
    notFound();
  }

  if (!entityData) notFound();

  let articles;
  let statsRes;
  let milestones: LegalMilestone[] = [];

  try {
    const [articlesRes, statsResult, rawMilestones] = await Promise.all([
      getEntityArticles(entityData.id, { page_size: 50 }),
      getEntityStats(entityData.id),
      getEntityMilestones(entityData.id).catch(() => []),
    ]);
    articles = articlesRes;
    statsRes = statsResult;
    milestones = rawMilestones.map(ncMilestoneToLegalMilestone);
  } catch (error) {
    console.error("[PoliticoPage] NC API error fetching details:", error);
    articles = { items: [], total: 0, page: 1, page_size: 50, pages: 1 };
    statsRes = null;
  }

  const politician = entityToPolitician(entityData, {
    entity_id: entityData.id,
    score: entityData.score,
    max_severity: entityData.max_severity,
    article_count: entityData.article_count,
  } as NCEntityScore);

  // Enrich milestoneCount with real data
  politician.milestoneCount = milestones.length;

  const frontendArticles = articles.items.map(ncArticleToArticle);
  const timelineItems = buildTimelineItems(frontendArticles, milestones);

  function getScoreLabel(score: number | null): string {
    if (score === null) return "Sem dados";
    if (score >= 80) return "Excelente";
    if (score >= 60) return "Bom";
    if (score >= 40) return "Regular";
    if (score >= 20) return "Preocupante";
    return "Crítico";
  }

  const canonicalUrl = `https://votolimpo.com.br/politico/${politician.slug}`;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: politician.name,
    url: canonicalUrl,
    jobTitle: politician.role,
    affiliation: {
      "@type": "Organization",
      name: politician.party,
    },
    description: `${politician.name} — ${politician.party} · ${politician.uf}. Índice de transparência: ${politician.score !== null ? `${politician.score}/100` : "N/D"}.`,
    ...(politician.photoUrl ? { image: politician.photoUrl } : {}),
  };

  function getScoreDescription(score: number | null): string {
    if (score === null) return "Ainda não há artigos processados suficientes para calcular o índice de transparência.";
    if (score >= 80) return "Este candidato apresenta alta transparência nos dados disponíveis.";
    if (score >= 60) return "Este candidato apresenta boa transparência com poucas ocorrências relevantes.";
    if (score >= 40) return "Este candidato apresenta transparência regular com algumas ocorrências relevantes.";
    if (score >= 20) return "Este candidato apresenta baixa transparência com múltiplas ocorrências graves.";
    return "Este candidato apresenta índice crítico com graves ocorrências documentadas.";
  }

  // Extract metadata for additional info
  const meta = entityData.metadata_json ? JSON.parse(entityData.metadata_json) : {};
  const coligacao = (meta.coligacao as string) || null;
  const situacao = (meta.situacao as string) || null;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, '\\u003c') }}
      />
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Back button */}
      <div className="mb-4 sm:mb-6">
        <Link
          href="/ranking"
          className="inline-flex items-center gap-2 text-sm text-[#6B7280] hover:text-[#FAFAFA] transition-colors"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Voltar ao ranking
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header Card — mobile-first stacked layout */}
          <div className="rounded-2xl border border-[#2E2E2E] bg-[#141414] p-4 sm:p-6">
            {/* Mobile: photo + score side by side at top */}
            <div className="flex items-start gap-4 mb-4">
              {/* Foto do candidato */}
              {politician.photoUrl ? (
                <Image
                  src={politician.photoUrl}
                  alt={politician.name}
                  width={96}
                  height={96}
                  className="h-20 w-20 sm:h-24 sm:w-24 flex-shrink-0 rounded-xl object-cover border border-[#2E2E2E]"
                  unoptimized
                />
              ) : (
                <div
                  className="flex h-20 w-20 sm:h-24 sm:w-24 flex-shrink-0 items-center justify-center rounded-xl border border-[#2E2E2E] text-2xl font-bold text-white"
                  style={{ backgroundColor: politician.partyColor + "CC" }}
                >
                  {politician.name.split(" ").filter(Boolean).map(p => p[0]).slice(0, 2).join("").toUpperCase()}
                </div>
              )}

              {/* Score badge — visible on mobile next to photo */}
              <div className="flex flex-col items-end gap-2 ml-auto">
                <ScoreBadge score={politician.score} size="lg" showLabel />
                <ShareButton title={`${politician.name} — Voto Limpo`} />
              </div>
            </div>

            {/* Name + info */}
            <div>
              <h1 className="text-2xl font-bold text-[#FAFAFA] sm:text-3xl md:text-4xl leading-tight">
                {politician.name}
              </h1>

              {politician.nomeUrna && politician.nomeUrna !== politician.name && (
                <p className="mt-1 text-sm text-[#9CA3AF]">
                  Nome de urna: <span className="font-semibold text-[#FAFAFA]">{politician.nomeUrna}</span>
                  {politician.numeroCandidato && (
                    <span className="ml-2 font-mono text-emerald-400">#{politician.numeroCandidato}</span>
                  )}
                </p>
              )}

              <p className="mt-2 text-[#6B7280]">{politician.role}</p>

              {/* Tags row */}
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <span
                  className="inline-flex items-center rounded-lg px-3 py-1 text-sm font-bold text-white"
                  style={{ backgroundColor: politician.partyColor + "CC" }}
                >
                  {politician.party}
                </span>
                {politician.uf && politician.uf !== "BR" && (
                  <span className="rounded-lg bg-[#2E2E2E] px-3 py-1 text-sm font-medium text-[#FAFAFA]">
                    {politician.uf}
                  </span>
                )}
                {politician.cargo && (
                  <span className="rounded-lg bg-[#1A2332] px-3 py-1 text-xs font-medium text-blue-300 border border-blue-500/20">
                    {politician.cargo.charAt(0).toUpperCase() + politician.cargo.slice(1).replace(/_/g, " ")}
                  </span>
                )}
                <SeverityBadge severity={politician.maxSeverity} size="md" />
                {situacao && (
                  <span className={`rounded-lg px-2 py-0.5 text-xs font-medium ${
                    situacao === "Deferido"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
                  }`}>
                    {situacao}
                  </span>
                )}
              </div>

              {coligacao && (
                <p className="mt-3 text-xs text-[#6B7280] leading-relaxed border-l-2 border-[#2E2E2E] pl-3">
                  Coligação: {coligacao}
                </p>
              )}
            </div>
          </div>

          {/* Mobile sidebar — score + stats appear between header and timeline on mobile */}
          <div className="grid grid-cols-2 gap-4 lg:hidden">
            {/* Score card (compact mobile) */}
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
              <h3 className="text-xs font-semibold text-[#6B7280] mb-2">Transparência</h3>
              <div className="text-center">
                <div className="font-mono text-3xl font-bold text-[#FAFAFA]">
                  {politician.score !== null ? politician.score : <span className="text-xl text-[#6B7280]">N/D</span>}
                  {politician.score !== null && <span className="text-sm text-[#6B7280]">/100</span>}
                </div>
                <p className="mt-1 text-xs font-medium" style={{
                  color: politician.score === null ? "#6B7280"
                    : politician.score >= 80 ? "#10B981"
                    : politician.score >= 60 ? "#3B82F6"
                    : politician.score >= 40 ? "#EAB308"
                    : politician.score >= 20 ? "#F97316"
                    : "#EF4444"
                }}>
                  {getScoreLabel(politician.score)}
                </p>
              </div>
            </div>

            {/* Stats card (compact mobile) */}
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
              <h3 className="text-xs font-semibold text-[#6B7280] mb-2">Estatísticas</h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#6B7280]">Artigos</span>
                  <span className="font-mono text-sm font-bold text-[#FAFAFA]">{politician.articleCount}</span>
                </div>
                {statsRes && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">7 dias</span>
                    <span className="font-mono text-sm font-bold text-[#FAFAFA]">{statsRes.articles.last_7d}</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#6B7280]">Severidade</span>
                  <SeverityBadge severity={politician.maxSeverity} size="sm" />
                </div>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-[#FAFAFA] sm:text-xl">
                Timeline ({timelineItems.length} eventos)
              </h2>
              <div className="hidden sm:flex items-center gap-2 text-xs text-[#6B7280]">
                <span className="inline-flex items-center gap-1">
                  <div className="h-3 w-3 rounded-full border-2 border-[#3E3E3E] bg-[#1A1A1A]" />
                  Artigo
                </span>
                <span className="inline-flex items-center gap-1">
                  <div className="h-3 w-3 rounded-full border-2 border-red-500 bg-red-500/10" />
                  Ocorrência jurídica
                </span>
              </div>
            </div>
            {timelineItems.length > 0 ? (
              <Timeline items={timelineItems} />
            ) : (
              <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-6 sm:p-8 text-center">
                <p className="text-sm text-[#6B7280]">
                  Nenhum artigo encontrado ainda para este candidato.
                  Os artigos estão sendo processados e vinculados automaticamente.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Desktop Sidebar — hidden on mobile (shown inline above) */}
        <div className="hidden lg:block space-y-6">
          {/* Score breakdown */}
          <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">
              Índice de Transparência
            </h3>

            <div className="text-center mb-4">
              <div className="font-mono text-5xl font-bold text-[#FAFAFA]">
                {politician.score !== null ? politician.score : <span className="text-3xl text-[#6B7280]">N/D</span>}
                {politician.score !== null && <span className="text-xl text-[#6B7280]">/100</span>}
              </div>
              <p className="mt-2 text-sm font-medium" style={{
                color: politician.score === null ? "#6B7280"
                  : politician.score >= 80 ? "#10B981"
                  : politician.score >= 60 ? "#3B82F6"
                  : politician.score >= 40 ? "#EAB308"
                  : politician.score >= 20 ? "#F97316"
                  : "#EF4444"
              }}>
                {getScoreLabel(politician.score)}
              </p>
            </div>

            {/* Score bar */}
            <div className="relative h-2 rounded-full bg-[#2E2E2E] overflow-hidden mb-3">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: politician.score !== null ? `${politician.score}%` : "0%",
                  background: politician.score === null
                    ? "#6B7280"
                    : politician.score >= 80
                    ? "#10B981"
                    : politician.score >= 60
                    ? "#3B82F6"
                    : politician.score >= 40
                    ? "#EAB308"
                    : politician.score >= 20
                    ? "#F97316"
                    : "#EF4444",
                }}
              />
            </div>

            <p className="text-xs text-[#6B7280] leading-relaxed">
              {getScoreDescription(politician.score)}
            </p>
          </div>

          {/* Stats */}
          <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">Estatísticas</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Artigos indexados</span>
                <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                  {politician.articleCount}
                </span>
              </div>
              {statsRes && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Fontes ativas</span>
                    <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                      {statsRes.sources.active}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Artigos (últimos 7 dias)</span>
                    <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                      {statsRes.articles.last_7d}
                    </span>
                  </div>
                </>
              )}
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Severidade máxima</span>
                <SeverityBadge severity={politician.maxSeverity} size="sm" />
              </div>
            </div>
          </div>

          {/* Candidate info */}
          {(politician.nomeUrna || coligacao) && (
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
              <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">Dados Eleitorais</h3>
              <div className="space-y-3">
                {politician.nomeUrna && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Nome de urna</span>
                    <span className="text-sm font-bold text-[#FAFAFA]">{politician.nomeUrna}</span>
                  </div>
                )}
                {politician.numeroCandidato && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Número</span>
                    <span className="font-mono text-sm font-bold text-emerald-400">{politician.numeroCandidato}</span>
                  </div>
                )}
                {politician.cargo && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Cargo</span>
                    <span className="text-sm font-medium text-[#FAFAFA]">
                      {politician.cargo.charAt(0).toUpperCase() + politician.cargo.slice(1).replace(/_/g, " ")}
                    </span>
                  </div>
                )}
                {situacao && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">Situação</span>
                    <span className={`text-sm font-medium ${situacao === "Deferido" ? "text-emerald-400" : "text-yellow-400"}`}>
                      {situacao}
                    </span>
                  </div>
                )}
                {coligacao && (
                  <div>
                    <span className="text-xs text-[#6B7280]">Coligação</span>
                    <p className="mt-1 text-xs text-[#9CA3AF] leading-relaxed">{coligacao}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
