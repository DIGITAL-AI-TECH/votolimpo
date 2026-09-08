import Link from "next/link";
import type { FC } from "react";
import type { Politician } from "@/types";
import ScoreBadge from "./ScoreBadge";
import SeverityBadge from "./SeverityBadge";

interface PoliticianCardProps {
  politician: Politician;
  rank?: number;
}

const PoliticianCard: FC<PoliticianCardProps> = ({ politician, rank }) => {
  return (
    <Link
      href={`/politico/${politician.slug}`}
      className="group block rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 transition-all duration-200 hover:border-emerald-500/50 hover:bg-[#1A1A1A] hover:shadow-lg hover:shadow-emerald-500/5"
    >
      <div className="flex items-start gap-3">
        {rank !== undefined && (
          <span className="flex-shrink-0 font-mono text-2xl font-bold text-[#2E2E2E] group-hover:text-emerald-500/30 transition-colors">
            {rank < 10 ? `0${rank}` : rank}
          </span>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-[#FAFAFA] group-hover:text-emerald-400 transition-colors">
                {politician.name}
              </h3>
              <p className="mt-0.5 truncate text-xs text-[#6B7280]">
                {politician.role}
              </p>
            </div>
            <ScoreBadge score={politician.score} size="sm" />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-bold text-white"
              style={{ backgroundColor: politician.partyColor + "CC" }}
            >
              {politician.party}
            </span>
            <span className="rounded bg-[#2E2E2E] px-2 py-0.5 text-xs text-[#6B7280]">
              {politician.uf}
            </span>
            <SeverityBadge severity={politician.maxSeverity} size="sm" />
          </div>

          <div className="mt-3 flex items-center gap-4 text-xs text-[#6B7280]">
            <span className="flex items-center gap-1">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
              </svg>
              {politician.articleCount} artigos
            </span>
            <span className="flex items-center gap-1">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
              </svg>
              {politician.milestoneCount} ocorrências
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
};

export default PoliticianCard;
