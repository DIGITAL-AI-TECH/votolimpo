"use client";

import { useEffect, useState, type FC } from "react";
import Link from "next/link";
import Image from "next/image";
import type { Politician, Article } from "@/types";
import PoliticianCard from "./PoliticianCard";
import ArticleCard from "./ArticleCard";
import ScoreBadge from "./ScoreBadge";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DashboardData {
  top: Politician[];
  total: number;
  distribution: { label: string; min: number; max: number; count: number; color: string }[];
  articles: Article[];
  cargo: string;
  uf: string | null;
}

interface ContextDashboardProps {
  cargo: string;
  uf?: string;
  onChangeContext: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CARGO_LABELS: Record<string, string> = {
  PRESIDENTE: "Presidente",
  GOVERNADOR: "Governador",
  SENADOR: "Senador",
  "DEPUTADO FEDERAL": "Deputado Federal",
  "DEPUTADO ESTADUAL": "Deputado Estadual",
};

const UF_NAMES: Record<string, string> = {
  AC:"Acre",AL:"Alagoas",AM:"Amazonas",AP:"Amapa",BA:"Bahia",CE:"Ceara",
  DF:"Distrito Federal",ES:"Espirito Santo",GO:"Goias",MA:"Maranhao",
  MG:"Minas Gerais",MS:"Mato Grosso do Sul",MT:"Mato Grosso",PA:"Para",
  PB:"Paraiba",PE:"Pernambuco",PI:"Piaui",PR:"Parana",RJ:"Rio de Janeiro",
  RN:"Rio Grande do Norte",RO:"Rondonia",RR:"Roraima",RS:"Rio Grande do Sul",
  SC:"Santa Catarina",SE:"Sergipe",SP:"Sao Paulo",TO:"Tocantins",
};

function cargoLabel(cargo: string): string {
  return CARGO_LABELS[cargo.toUpperCase()] || cargo;
}

function contextLabel(cargo: string, uf?: string): string {
  const c = cargoLabel(cargo);
  if (!uf) return `Candidatos a ${c}`;
  return `Candidatos a ${c} em ${UF_NAMES[uf] || uf}`;
}

function getInitials(name: string): string {
  const parts = name.split(" ").filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-full bg-[#2E2E2E]" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-32 rounded bg-[#2E2E2E]" />
          <div className="h-3 w-20 rounded bg-[#2E2E2E]" />
        </div>
        <div className="h-8 w-16 rounded-lg bg-[#2E2E2E]" />
      </div>
    </div>
  );
}

function SkeletonBars() {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="h-3 w-24 rounded bg-[#2E2E2E]" />
          <div className="h-3 flex-1 rounded bg-[#2E2E2E]" style={{ maxWidth: `${80 - i * 15}%` }} />
        </div>
      ))}
    </div>
  );
}

// Top-3 hero card for first place
function TopHeroCard({ politician, medal }: { politician: Politician; medal: string }) {
  const [imgError, setImgError] = useState(false);
  const hasPhoto = politician.photoUrl && !imgError;

  return (
    <Link
      href={`/politico/${politician.slug}`}
      className="group block rounded-xl border border-emerald-500/20 bg-gradient-to-br from-[#141414] to-emerald-500/5 p-5 transition-all hover:border-emerald-500/40 hover:shadow-lg hover:shadow-emerald-500/5"
    >
      <div className="flex items-center gap-4">
        <span className="text-2xl">{medal}</span>
        <div className="relative h-14 w-14 flex-shrink-0 overflow-hidden rounded-full border-2 border-emerald-500/30">
          {hasPhoto ? (
            <Image
              src={politician.photoUrl!}
              alt={politician.name}
              fill
              className="object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-[#2E2E2E] text-sm font-bold text-[#FAFAFA]">
              {getInitials(politician.name)}
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-base font-bold text-[#FAFAFA] truncate group-hover:text-emerald-400 transition-colors">
            {politician.nomeUrna || politician.name}
          </p>
          <p className="text-xs text-[#6B7280]">
            {politician.party} · {politician.uf}
            {politician.cargo ? ` · ${politician.cargo}` : ""}
          </p>
          <p className="mt-1 text-xs text-[#6B7280]">
            {politician.articleCount} {politician.articleCount === 1 ? "noticia" : "noticias"} analisadas
          </p>
        </div>
        <ScoreBadge score={politician.score} size="lg" />
      </div>
    </Link>
  );
}

function MiniCard({ politician, medal }: { politician: Politician; medal: string }) {
  const [imgError, setImgError] = useState(false);
  const hasPhoto = politician.photoUrl && !imgError;

  return (
    <Link
      href={`/politico/${politician.slug}`}
      className="group block rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 transition-all hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
    >
      <div className="text-center">
        <span className="text-lg">{medal}</span>
        <div className="mx-auto mt-2 relative h-12 w-12 overflow-hidden rounded-full border border-[#2E2E2E]">
          {hasPhoto ? (
            <Image
              src={politician.photoUrl!}
              alt={politician.name}
              fill
              className="object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-[#2E2E2E] text-xs font-bold text-[#FAFAFA]">
              {getInitials(politician.name)}
            </div>
          )}
        </div>
        <p className="mt-2 text-sm font-semibold text-[#FAFAFA] truncate group-hover:text-emerald-400 transition-colors">
          {politician.nomeUrna || politician.name}
        </p>
        <p className="text-xs text-[#6B7280]">{politician.party}</p>
        <div className="mt-2">
          <ScoreBadge score={politician.score} size="sm" />
        </div>
      </div>
    </Link>
  );
}

// Distribution bar chart (pure CSS)
function DistributionChart({
  distribution,
  total,
}: {
  distribution: DashboardData["distribution"];
  total: number;
}) {
  const maxCount = Math.max(...distribution.map((d) => d.count), 1);

  return (
    <div className="space-y-3">
      {distribution.map((range) => (
        <div key={range.label} className="flex items-center gap-3">
          <span className="w-28 text-xs text-[#6B7280] flex-shrink-0">
            {range.label} ({range.min}-{range.max})
          </span>
          <div className="flex-1 h-4 rounded-full bg-[#1A1A1A] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out"
              style={{
                width: `${Math.max((range.count / maxCount) * 100, range.count > 0 ? 8 : 0)}%`,
                backgroundColor: range.color,
              }}
            />
          </div>
          <span className="w-6 text-right text-xs font-mono text-[#FAFAFA]">
            {range.count}
          </span>
        </div>
      ))}
      <p className="text-xs text-[#6B7280] text-center mt-2">
        Total: {total} candidatos
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const ContextDashboard: FC<ContextDashboardProps> = ({ cargo, uf, onChangeContext }) => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);

    const params = new URLSearchParams();
    params.set("cargo", cargo);
    if (uf) params.set("uf", uf);

    fetch(`/api/dashboard?${params.toString()}`)
      .then((r) => {
        if (!r.ok) throw new Error("API error");
        return r.json();
      })
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [cargo, uf]);

  const top3 = data?.top.slice(0, 3) ?? [];
  const rest = data?.top.slice(3) ?? [];
  const medals = ["\u{1F947}", "\u{1F948}", "\u{1F949}"]; // gold, silver, bronze

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Context badge */}
      <div className="mb-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5">
            <svg className="h-4 w-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-sm font-medium text-emerald-400">
              {contextLabel(cargo, uf)}
            </span>
          </div>
          <p className="mt-2 text-xs text-[#6B7280]">
            Eleicoes 2026 · Dados atualizados automaticamente
          </p>
        </div>
        <button
          onClick={onChangeContext}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5 text-xs text-[#FAFAFA] transition-colors hover:border-emerald-500/50 hover:bg-[#1A1A1A]"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Mudar cargo/estado
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-6">
          <div className="space-y-3">
            <SkeletonCard />
            <div className="grid grid-cols-2 gap-3">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          </div>
          <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
            <SkeletonBars />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
          <p className="text-sm text-red-400">Erro ao carregar dados. Tente novamente.</p>
          <button
            onClick={() => { setError(false); setLoading(true); }}
            className="mt-3 rounded-lg bg-red-500/20 px-4 py-2 text-xs text-red-400 hover:bg-red-500/30"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Data loaded */}
      {!loading && !error && data && (
        <div className="space-y-8">
          {/* Top 3 */}
          {top3.length > 0 ? (
            <section>
              <h2 className="mb-4 text-lg font-bold text-[#FAFAFA]">
                Top candidatos mais transparentes
              </h2>
              <div className="space-y-3">
                {top3[0] && <TopHeroCard politician={top3[0]} medal={medals[0]} />}
                {top3.length > 1 && (
                  <div className="grid grid-cols-2 gap-3">
                    {top3[1] && <MiniCard politician={top3[1]} medal={medals[1]} />}
                    {top3[2] && <MiniCard politician={top3[2]} medal={medals[2]} />}
                  </div>
                )}
              </div>
            </section>
          ) : (
            <section className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-8 text-center">
              <p className="text-sm text-[#6B7280]">
                Ainda estamos coletando dados sobre candidatos a {cargoLabel(cargo)}
                {uf ? ` em ${UF_NAMES[uf] || uf}` : ""}.
              </p>
              <p className="mt-2 text-xs text-[#6B7280]">
                Volte em breve — novas noticias sao analisadas automaticamente.
              </p>
            </section>
          )}

          {/* Score distribution */}
          {data.distribution.some((d) => d.count > 0) && (
            <section className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-5">
              <h3 className="mb-4 text-sm font-semibold text-[#FAFAFA]">
                Distribuicao de transparencia
              </h3>
              <DistributionChart distribution={data.distribution} total={data.total} />
            </section>
          )}

          {/* More candidates */}
          {rest.length > 0 && (
            <section>
              <h3 className="mb-4 text-sm font-semibold text-[#FAFAFA]">
                Mais candidatos
              </h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {rest.map((p, i) => (
                  <PoliticianCard key={p.id} politician={p} rank={i + 4} />
                ))}
              </div>
            </section>
          )}

          {/* CTA ranking completo */}
          <div className="text-center">
            <Link
              href={`/ranking?cargo=${encodeURIComponent(cargo)}${uf ? `&uf=${uf}` : ""}`}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-600"
            >
              Ver ranking completo
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

          {/* Recent articles */}
          {data.articles.length > 0 && (
            <section className="border-t border-[#1A1A1A] pt-8">
              <h3 className="mb-4 text-lg font-bold text-[#FAFAFA]">
                Noticias recentes
              </h3>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {data.articles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
};

export default ContextDashboard;
