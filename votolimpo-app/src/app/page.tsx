import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import {
  getGlobalStats,
  getVotoLimpoStats,
  listEntities,
  listArticles,
  ncStatsToStats,
  entityToPolitician,
  ncArticleToArticle,
} from "@/lib/nc-api";
import PoliticianCard from "@/components/PoliticianCard";
import ArticleCard from "@/components/ArticleCard";
import SearchBar from "@/components/SearchBar";
import HomeClient from "@/components/HomeClient";
import type { Politician, Article, Stats } from "@/types";

export const revalidate = 60; // ISR: regenerate every 60s

export const metadata: Metadata = {
  title: "Voto Limpo — Transparência Política Brasileira | Eleições 2026",
  description:
    "Plataforma de transparência política com inteligência artificial. Acompanhe candidatos das Eleições 2026, índice de transparência, notícias verificadas e mapa de partidos. Dados públicos e acessíveis.",
  alternates: {
    canonical: "https://votolimpo.com.br",
  },
  openGraph: {
    type: "website",
    url: "https://votolimpo.com.br",
    title: "Voto Limpo — Transparência Política Brasileira | Eleições 2026",
    description:
      "Plataforma de transparência política com IA. Candidatos, notícias verificadas e índice de transparência das Eleições 2026.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Voto Limpo — Transparência Política Brasileira | Eleições 2026",
    description:
      "Plataforma de transparência política com IA. Dados públicos, verificados e acessíveis.",
  },
};

function daysUntilElection(): number {
  const electionDay = new Date("2026-10-04T00:00:00-03:00");
  const now = new Date();
  const diffMs = electionDay.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat("pt-BR").format(n);
}

export default async function HomePage() {
  let stats: Stats;
  let top10: Politician[];
  let recentArticles: Article[];

  try {
    const [ncStats, vlStats, entities, articlesRes] = await Promise.all([
      getGlobalStats(),
      getVotoLimpoStats(),
      listEntities({ type: "candidate", active: true, limit: 50, order_by: "article_count", order_dir: "desc" }),
      listArticles({ status: "processed", page_size: 6 }),
    ]);

    stats = ncStatsToStats(ncStats, vlStats);

    top10 = entities
      .map((e) => entityToPolitician(e))
      .sort((a, b) => b.articleCount - a.articleCount || a.name.localeCompare(b.name))
      .slice(0, 10);

    recentArticles = articlesRes.items.map(ncArticleToArticle);
  } catch (error) {
    console.error("[HomePage] NC API error:", error);
    stats = {
      totalPoliticians: 0,
      totalArticles: 0,
      totalEntities: 0,
      totalSources: 0,
      avgScore: null,
      criticalCount: 0,
    };
    top10 = [];
    recentArticles = [];
  }

  const daysLeft = daysUntilElection();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Voto Limpo",
    url: "https://votolimpo.com.br",
    description:
      "Plataforma de transparência política brasileira com IA. Eleições 2026.",
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://votolimpo.com.br/busca?q={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
    publisher: {
      "@type": "Organization",
      name: "Voto Limpo",
      url: "https://votolimpo.com.br",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, '\\u003c') }}
      />
    <div className="min-h-screen">
      {/* Hero Section — always visible */}
      <section className="relative overflow-hidden border-b border-[#1A1A1A] py-16 md:py-28">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,_#10B98115_0%,_transparent_70%)]" />

        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          {/* Election countdown badge */}
          <div className="mb-6 inline-flex items-center gap-3 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-5 py-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">
              Eleições 2026
            </span>
            <span className="h-4 w-px bg-emerald-500/30" />
            <span className="font-mono text-xs font-bold text-emerald-300">
              {daysLeft > 0 ? `${daysLeft} dias para o 1° turno` : "Dia da eleição!"}
            </span>
          </div>

          <h1 className="text-4xl font-bold tracking-tight text-[#FAFAFA] sm:text-5xl md:text-6xl">
            Conheça seus candidatos{" "}
            <span className="text-emerald-400">antes de votar</span>
          </h1>

          <p className="mt-6 text-lg text-[#6B7280] max-w-2xl mx-auto leading-relaxed">
            Plataforma independente que usa inteligência artificial para analisar notícias
            e gerar um índice de transparência para cada candidato. Dados públicos, verificados
            e acessíveis para todo cidadão.
          </p>

          {/* Search */}
          <div className="mt-10 mx-auto max-w-xl">
            <SearchBar placeholder="Buscar candidato por nome, partido ou estado..." />
          </div>

          {/* Quick stats */}
          <div className="mt-10 grid grid-cols-2 gap-4 sm:flex sm:flex-wrap sm:items-center sm:justify-center sm:gap-8">
            {[
              { value: formatNumber(stats.totalPoliticians), label: "Candidatos monitorados" },
              { value: formatNumber(stats.totalArticles), label: "Notícias analisadas por IA" },
              { value: formatNumber(stats.totalSources), label: "Fontes de notícias" },
              { value: stats.avgScore !== null ? `${stats.avgScore.toFixed(0)}/100` : "N/D", label: "Índice médio de transparência" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="font-mono text-2xl font-bold text-[#FAFAFA] sm:text-3xl">
                  {stat.value}
                </p>
                <p className="mt-1 text-xs text-[#6B7280]">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Journey-aware client wrapper: shows dashboard if context exists, or quiz CTA + default content */}
      <HomeClient>

      {/* How it works — IA Section */}
      <section className="border-b border-[#1A1A1A] py-14">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold text-[#FAFAFA]">
              Como a IA analisa os candidatos
            </h2>
            <p className="mt-2 text-sm text-[#6B7280] max-w-2xl mx-auto">
              Nosso sistema coleta notícias automaticamente, processa com inteligência artificial
              e gera indicadores de transparência para cada político
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              {
                icon: (
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                  </svg>
                ),
                title: "Coleta automática",
                desc: `${formatNumber(stats.totalSources)} fontes monitoradas 24h por dia. Notícias coletadas e deduplicadas em tempo real.`,
              },
              {
                icon: (
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-2.47 2.47a3.375 3.375 0 01-4.76 0L9.5 14.5m9.5 0V17a2.25 2.25 0 01-2.25 2.25H7.25A2.25 2.25 0 015 17v-2.5" />
                  </svg>
                ),
                title: "Análise com IA",
                desc: `${formatNumber(stats.totalArticles)} notícias processadas. A IA extrai menções a candidatos, avalia veracidade e identifica ocorrências.`,
              },
              {
                icon: (
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                  </svg>
                ),
                title: "Índice de transparência",
                desc: `Cada candidato recebe uma nota de 0 a 100 baseada na cobertura midiática. ${stats.criticalCount > 0 ? `${stats.criticalCount} com ocorrências críticas.` : "Tudo transparente."}`,
              },
            ].map((step) => (
              <div
                key={step.title}
                className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5"
              >
                <div className="mb-3 inline-flex items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-2.5 text-emerald-400">
                  {step.icon}
                </div>
                <h3 className="text-sm font-semibold text-[#FAFAFA]">{step.title}</h3>
                <p className="mt-1.5 text-xs text-[#6B7280] leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 text-center">
            <Link
              href="/como-funciona"
              className="inline-flex items-center gap-1.5 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Saiba mais sobre a metodologia
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* Top 10 Ranking */}
      <section className="py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-[#FAFAFA]">Candidatos em Destaque</h2>
              <p className="mt-1 text-sm text-[#6B7280]">
                Candidatos com maior cobertura midiática nas Eleições 2026
              </p>
            </div>
            <Link
              href="/ranking"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-[#2E2E2E] bg-[#141414] px-4 py-2 text-sm text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
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
              <p className="text-[#6B7280]">Nenhum candidato disponível no momento.</p>
            </div>
          )}

          <div className="mt-6 text-center sm:hidden">
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
        </div>
      </section>

      {/* Recent Articles */}
      <section className="border-t border-[#1A1A1A] py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-[#FAFAFA]">Notícias Recentes</h2>
              <p className="mt-1 text-sm text-[#6B7280]">
                Últimas reportagens analisadas pela nossa inteligência artificial
              </p>
            </div>
            <Link
              href="/busca"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-[#2E2E2E] bg-[#141414] px-4 py-2 text-sm text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
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
              <p className="text-[#6B7280]">Nenhum artigo disponível no momento.</p>
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t border-[#1A1A1A] py-14">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-[#2E2E2E] bg-[#141414] p-8 md:p-12">
            <Image
              src="/logo-site.png"
              alt="Voto Limpo"
              width={64}
              height={64}
              className="mx-auto mb-6 rounded-xl"
            />
            <h2 className="text-2xl font-bold text-[#FAFAFA] md:text-3xl">
              Explore o mapa de partidos
            </h2>
            <p className="mt-4 text-[#6B7280] max-w-lg mx-auto">
              Visualize como os candidatos se distribuem entre os partidos e descubra as conexões
              entre políticos e organizações
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/grafo"
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-600"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Ver mapa de partidos
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

      </HomeClient>
    </div>
    </>
  );
}
