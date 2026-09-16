import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { unstable_noStore } from "next/cache";
import {
  getEntityBySlug,
  getEntityArticles,
  getEntityStats,
  entityToPolitician,
  ncArticleToArticle,
  type NCEntityScore,
} from "@/lib/nc-api";
import ScoreBadge from "@/components/ScoreBadge";
import SeverityBadge from "@/components/SeverityBadge";
import ShareButton from "@/components/ShareButton";
import Timeline, { buildTimelineItems } from "@/components/Timeline";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  unstable_noStore();
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
    const description = `Perfil completo de ${politician.name} — ${politician.party} · ${politician.uf}. Consulte o historico, vinculos e o indice de transparencia no Voto Limpo.`;
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
  unstable_noStore();
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

  try {
    [articles, statsRes] = await Promise.all([
      getEntityArticles(entityData.id, { page_size: 50 }),
      getEntityStats(entityData.id),
    ]);
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

  const frontendArticles = articles.items.map(ncArticleToArticle);
  const timelineItems = buildTimelineItems(frontendArticles, []);

  function getScoreLabel(score: number): string {
    if (score >= 80) return "Excelente";
    if (score >= 60) return "Bom";
    if (score >= 40) return "Regular";
    if (score >= 20) return "Preocupante";
    return "Critico";
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
    description: `${politician.name} — ${politician.party} · ${politician.uf}. Indice de transparencia: ${politician.score}/100.`,
    ...(politician.photoUrl ? { image: politician.photoUrl } : {}),
  };

  function getScoreDescription(score: number): string {
    if (score >= 80) return "Este candidato apresenta alta transparencia nos dados disponiveis.";
    if (score >= 60) return "Este candidato apresenta boa transparencia com poucas ocorrencias relevantes.";
    if (score >= 40) return "Este candidato apresenta transparencia regular com algumas ocorrencias relevantes.";
    if (score >= 20) return "Este candidato apresenta baixa transparencia com multiplas ocorrencias graves.";
    return "Este candidato apresenta indice critico com graves ocorrencias documentadas.";
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Back button */}
      <div className="mb-6">
        <a
          href="/ranking"
          className="inline-flex items-center gap-2 text-sm text-[#6B7280] hover:text-[#FAFAFA] transition-colors"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Voltar ao ranking
        </a>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header Card */}
          <div className="rounded-2xl border border-[#2E2E2E] bg-[#141414] p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span
                    className="inline-flex items-center rounded-lg px-3 py-1 text-sm font-bold text-white"
                    style={{ backgroundColor: politician.partyColor + "CC" }}
                  >
                    {politician.party}
                  </span>
                  <span className="rounded-lg bg-[#2E2E2E] px-3 py-1 text-sm font-medium text-[#FAFAFA]">
                    {politician.uf}
                  </span>
                  <SeverityBadge severity={politician.maxSeverity} size="md" />
                </div>

                <h1 className="text-3xl font-bold text-[#FAFAFA] md:text-4xl">
                  {politician.name}
                </h1>
                <p className="mt-2 text-[#6B7280]">{politician.role}</p>

                {politician.bio && (
                  <p className="mt-4 text-sm text-[#6B7280] leading-relaxed border-l-2 border-[#2E2E2E] pl-4">
                    {politician.bio}
                  </p>
                )}
              </div>

              <div className="flex flex-col items-end gap-3">
                <ScoreBadge score={politician.score} size="lg" showLabel />
                <ShareButton title={`${politician.name} — Voto Limpo`} />
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-[#FAFAFA]">
                Timeline ({timelineItems.length} eventos)
              </h2>
              <div className="flex items-center gap-2 text-xs text-[#6B7280]">
                <span className="inline-flex items-center gap-1">
                  <div className="h-3 w-3 rounded-full border-2 border-[#3E3E3E] bg-[#1A1A1A]" />
                  Artigo
                </span>
                <span className="inline-flex items-center gap-1">
                  <div className="h-3 w-3 rounded-full border-2 border-red-500 bg-red-500/10" />
                  Ocorrencia juridica
                </span>
              </div>
            </div>
            {timelineItems.length > 0 ? (
              <Timeline items={timelineItems} />
            ) : (
              <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-8 text-center">
                <p className="text-[#6B7280]">
                  Nenhum artigo encontrado ainda para este candidato.
                  Os artigos estao sendo processados e vinculados automaticamente.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Score breakdown */}
          <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">
              Indice de Transparencia
            </h3>

            <div className="text-center mb-4">
              <div className="font-mono text-5xl font-bold text-[#FAFAFA]">
                {politician.score}
                <span className="text-xl text-[#6B7280]">/100</span>
              </div>
              <p className="mt-2 text-sm font-medium text-emerald-400">
                {getScoreLabel(politician.score)}
              </p>
            </div>

            {/* Score bar */}
            <div className="relative h-2 rounded-full bg-[#2E2E2E] overflow-hidden mb-3">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${politician.score}%`,
                  background: politician.score >= 80
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
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">Estatisticas</h3>
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
                    <span className="text-xs text-[#6B7280]">Artigos (ultimos 7 dias)</span>
                    <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                      {statsRes.articles.last_7d}
                    </span>
                  </div>
                </>
              )}
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Severidade maxima</span>
                <SeverityBadge severity={politician.maxSeverity} size="sm" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </>
  );
}
