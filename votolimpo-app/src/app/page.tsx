import Link from "next/link";
import { unstable_noStore } from "next/cache";
import {
  getGlobalStats,
  listEntities,
  listArticles,
  ncStatsToStats,
  entityToPolitician,
  ncArticleToArticle,
} from "@/lib/nc-api";
import PoliticianCard from "@/components/PoliticianCard";
import ArticleCard from "@/components/ArticleCard";
import SearchBar from "@/components/SearchBar";
import type { Politician, Article, Stats } from "@/types";

export const dynamic = "force-dynamic";
export const revalidate = 120;

export default async function HomePage() {
  unstable_noStore();
  let stats: Stats;
  let top10: Politician[];
  let recentArticles: Article[];

  try {
    const [ncStats, entities, articlesRes] = await Promise.all([
      getGlobalStats(),
      listEntities({ type: "candidate", active: true, limit: 50 }),
      listArticles({ status: "processed", page_size: 6 }),
    ]);

    stats = ncStatsToStats(ncStats);

    // Sort by name for now (score will come from processing later)
    top10 = entities
      .map((e) => entityToPolitician(e))
      .sort((a, b) => a.name.localeCompare(b.name))
      .slice(0, 10);

    recentArticles = articlesRes.items.map(ncArticleToArticle);
  } catch (error) {
    console.error("[HomePage] NC API error:", error);
    stats = {
      totalPoliticians: 0,
      totalArticles: 0,
      totalEntities: 0,
      totalRelationships: 0,
      avgScore: 0,
      criticalCount: 0,
    };
    top10 = [];
    recentArticles = [];
  }

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-[#1A1A1A] py-20 md:py-32">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,_#10B98115_0%,_transparent_70%)]" />

        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          {/* Badge */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">
              Dados atualizados · {new Date().toLocaleDateString("pt-BR")}
            </span>
          </div>

          <h1 className="text-4xl font-bold tracking-tight text-[#FAFAFA] sm:text-5xl md:text-6xl">
            Transparencia politica{" "}
            <span className="text-emerald-400">ao alcance</span>
            <br />
            de todos
          </h1>

          <p className="mt-6 text-lg text-[#6B7280] max-w-2xl mx-auto leading-relaxed">
            Acompanhe o historico de processos, vinculos empresariais e o indice de
            transparencia dos politicos brasileiros. Dados publicos, verificados e acessiveis.
          </p>

          {/* Search */}
          <div className="mt-10 mx-auto max-w-xl">
            <SearchBar placeholder="Buscar politico por nome, partido ou estado..." />
          </div>

          {/* Quick stats */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-6 md:gap-10">
            {[
              { value: stats.totalPoliticians.toLocaleString("pt-BR"), label: "Politicos monitorados" },
              { value: stats.totalArticles.toLocaleString("pt-BR"), label: "Artigos indexados" },
              { value: stats.totalRelationships.toLocaleString("pt-BR"), label: "Fontes mapeadas" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="font-mono text-3xl font-bold text-[#FAFAFA]">
                  {stat.value}+
                </p>
                <p className="mt-1 text-xs text-[#6B7280]">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Top 10 Ranking */}
      <section className="py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-[#FAFAFA]">Candidatos em Destaque</h2>
              <p className="mt-1 text-sm text-[#6B7280]">
                Candidatos com maior cobertura midiática baseada em dados publicos
              </p>
            </div>
            <Link
              href="/ranking"
              className="inline-flex items-center gap-2 rounded-lg border border-[#2E2E2E] bg-[#141414] px-4 py-2 text-sm text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
            >
              Ver ranking completo
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

          {top10.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {top10.map((politician, index) => (
                <PoliticianCard
                  key={politician.id}
                  politician={politician}
                  rank={index + 1}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-12 text-center">
              <p className="text-[#6B7280]">Carregando dados de candidatos...</p>
            </div>
          )}
        </div>
      </section>

      {/* Recent Articles */}
      <section className="border-t border-[#1A1A1A] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-[#FAFAFA]">Noticias Recentes</h2>
              <p className="mt-1 text-sm text-[#6B7280]">
                Ultimas reportagens sobre politica e transparencia
              </p>
            </div>
            <Link
              href="/busca"
              className="inline-flex items-center gap-2 rounded-lg border border-[#2E2E2E] bg-[#141414] px-4 py-2 text-sm text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
            >
              Ver todas
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

          {recentArticles.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {recentArticles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-12 text-center">
              <p className="text-[#6B7280]">Artigos estao sendo processados...</p>
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t border-[#1A1A1A] py-16">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-[#2E2E2E] bg-[#141414] p-8 md:p-12">
            <h2 className="text-2xl font-bold text-[#FAFAFA] md:text-3xl">
              Explore os vinculos politicos
            </h2>
            <p className="mt-4 text-[#6B7280]">
              Visualize em tempo real as conexoes entre politicos e entidades no grafo interativo
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/grafo"
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-600"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Ver grafo de vinculos
              </Link>
              <Link
                href="/ranking"
                className="inline-flex items-center gap-2 rounded-xl border border-[#2E2E2E] bg-[#0A0A0A] px-6 py-3 text-sm font-semibold text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
              >
                Ver ranking completo
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
