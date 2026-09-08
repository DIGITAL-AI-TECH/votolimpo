import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  POLITICIANS,
  getPoliticianBySlug,
  getArticlesForPolitician,
  getMilestonesForPolitician,
  getRelationshipsForPolitician,
} from "@/lib/mock-data";
import { ENTITIES } from "@/lib/mock-data";
import ScoreBadge from "@/components/ScoreBadge";
import SeverityBadge from "@/components/SeverityBadge";
import ShareButton from "@/components/ShareButton";
import Timeline, { buildTimelineItems } from "@/components/Timeline";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return POLITICIANS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const politician = getPoliticianBySlug(slug);
  if (!politician) return { title: "Não encontrado" };

  return {
    title: politician.name,
    description: `Perfil de ${politician.name} — ${politician.party} · ${politician.uf}. Índice de transparência: ${politician.score}/100.`,
  };
}

export default async function PoliticoPage({ params }: PageProps) {
  const { slug } = await params;
  const politician = getPoliticianBySlug(slug);

  if (!politician) notFound();

  const articles = getArticlesForPolitician(politician.id);
  const milestones = getMilestonesForPolitician(politician.id);
  const relationships = getRelationshipsForPolitician(politician.id);
  const timelineItems = buildTimelineItems(articles, milestones);

  const relatedEntities = relationships.map((r) => {
    const entity = ENTITIES.find((e) => e.id === r.entityId);
    return { relationship: r, entity };
  });

  function getScoreLabel(score: number): string {
    if (score >= 80) return "Excelente";
    if (score >= 60) return "Bom";
    if (score >= 40) return "Regular";
    if (score >= 20) return "Preocupante";
    return "Crítico";
  }

  function getScoreDescription(score: number): string {
    if (score >= 80) return "Este político apresenta alta transparência nos dados disponíveis.";
    if (score >= 60) return "Este político apresenta boa transparência com poucas ocorrências relevantes.";
    if (score >= 40) return "Este político apresenta transparência regular com algumas ocorrências relevantes.";
    if (score >= 20) return "Este político apresenta baixa transparência com múltiplas ocorrências graves.";
    return "Este político apresenta índice crítico com graves ocorrências documentadas.";
  }

  const entityTypeLabel: Record<string, string> = {
    company: "Empresa",
    organization: "Organização",
    government: "Governo",
    ngo: "ONG",
    media: "Mídia",
  };

  const relTypeLabel: Record<string, string> = {
    donation: "Doação",
    contract: "Contrato",
    board_member: "Conselho",
    investigation: "Investigação",
    business_partner: "Parceria",
    family: "Família",
  };

  return (
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
                  Ocorrência jurídica
                </span>
              </div>
            </div>
            <Timeline items={timelineItems} />
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Score breakdown */}
          <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">
              Índice de Transparência
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
            <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">Estatísticas</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Artigos indexados</span>
                <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                  {politician.articleCount}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Ocorrências jurídicas</span>
                <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                  {politician.milestoneCount}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Vínculos mapeados</span>
                <span className="font-mono text-sm font-bold text-[#FAFAFA]">
                  {relationships.length}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7280]">Severidade máxima</span>
                <SeverityBadge severity={politician.maxSeverity} size="sm" />
              </div>
            </div>
          </div>

          {/* Related Entities */}
          {relatedEntities.length > 0 && (
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
              <h3 className="text-sm font-semibold text-[#FAFAFA] mb-4">
                Vínculos ({relatedEntities.length})
              </h3>
              <div className="space-y-3">
                {relatedEntities.map(({ relationship, entity }) =>
                  entity ? (
                    <div key={relationship.id} className="rounded-lg bg-[#0A0A0A] p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-[#FAFAFA] leading-snug">
                            {entity.name}
                          </p>
                          <p className="mt-0.5 text-xs text-[#6B7280]">
                            {entityTypeLabel[entity.type]}
                          </p>
                        </div>
                        <span className="flex-shrink-0 rounded bg-[#242424] px-1.5 py-0.5 text-xs text-[#6B7280]">
                          {relTypeLabel[relationship.type]}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-[#6B7280] leading-relaxed line-clamp-2">
                        {relationship.description}
                      </p>
                    </div>
                  ) : null
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-[#2E2E2E]">
                <a
                  href="/grafo"
                  className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  Ver no grafo de vínculos
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
