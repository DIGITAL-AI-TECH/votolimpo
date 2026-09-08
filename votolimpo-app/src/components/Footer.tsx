import Link from "next/link";
import type { FC } from "react";
import type { Stats } from "@/types";

interface FooterProps {
  stats?: Stats;
}

const Footer: FC<FooterProps> = ({ stats }) => {
  return (
    <footer className="mt-auto border-t border-[#2E2E2E] bg-[#0A0A0A]">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {stats && (
          <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6 rounded-xl border border-[#1A1A1A] bg-[#141414] p-4">
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-emerald-400">{stats.totalPoliticians}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Políticos</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-blue-400">{stats.totalArticles}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Artigos</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-purple-400">{stats.totalEntities}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Entidades</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-yellow-400">{stats.totalRelationships}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Vínculos</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-[#FAFAFA]">{stats.avgScore}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Score Médio</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold text-red-400">{stats.criticalCount}</p>
              <p className="mt-1 text-xs text-[#6B7280]">Críticos</p>
            </div>
          </div>
        )}

        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-emerald-500/10 border border-emerald-500/30">
              <svg className="h-3 w-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-[#FAFAFA]">
              Voto<span className="text-emerald-400">Limpo</span>
            </span>
          </div>

          <nav className="flex items-center gap-4">
            <Link href="/" className="text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors">Início</Link>
            <Link href="/ranking" className="text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors">Ranking</Link>
            <Link href="/busca" className="text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors">Busca</Link>
            <Link href="/grafo" className="text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors">Grafo</Link>
          </nav>

          <p className="text-xs text-[#6B7280]">
            © {new Date().getFullYear()} Voto Limpo — Dados públicos
          </p>
        </div>

        <div className="mt-4 text-center">
          <p className="text-xs text-[#3E3E3E]">
            Os dados apresentados são de domínio público e têm caráter informativo. As informações sobre processos judiciais referem-se a fatos de interesse público.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
