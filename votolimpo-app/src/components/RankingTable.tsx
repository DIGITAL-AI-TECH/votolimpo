"use client";

import Link from "next/link";
import { type FC } from "react";
import type { Politician, SortField, SortOrder } from "@/types";
import ScoreBadge from "./ScoreBadge";
import SeverityBadge from "./SeverityBadge";

interface RankingTableProps {
  politicians: Politician[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onSortChange: (field: SortField, order: SortOrder) => void;
  sortField: SortField;
  sortOrder: SortOrder;
}

const COLUMNS: { key: SortField; label: string }[] = [
  { key: "name", label: "Candidato" },
  { key: "party", label: "Partido" },
  { key: "uf", label: "Estado" },
  { key: "score", label: "Transparência" },
  { key: "articleCount", label: "Notícias" },
  { key: "maxSeverity", label: "Gravidade" },
];

const RankingTable: FC<RankingTableProps> = ({
  politicians,
  total,
  page,
  pageSize,
  onPageChange,
  onSortChange,
  sortField,
  sortOrder,
}) => {
  const totalPages = Math.ceil(total / pageSize);

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      onSortChange(field, sortOrder === "asc" ? "desc" : "asc");
    } else {
      onSortChange(field, "asc");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Mobile cards (visible below md) */}
      <div className="flex flex-col gap-3 md:hidden">
        {politicians.map((politician, index) => {
          const rowNum = (page - 1) * pageSize + index + 1;
          return (
            <Link
              key={politician.id}
              href={`/politico/${politician.slug}`}
              className="block rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 transition-colors hover:border-emerald-500/50"
            >
              <div className="flex items-start gap-3">
                <span className="flex-shrink-0 font-mono text-lg font-bold text-[#2E2E2E]">
                  {rowNum < 10 ? `0${rowNum}` : rowNum}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#FAFAFA]">{politician.name}</p>
                      <p className="truncate text-xs text-[#6B7280]">{politician.role}</p>
                    </div>
                    <ScoreBadge score={politician.score} size="sm" />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      className="inline-flex items-center rounded px-2 py-0.5 text-xs font-bold text-white"
                      style={{ backgroundColor: politician.partyColor + "CC" }}
                    >
                      {politician.party}
                    </span>
                    <span className="rounded bg-[#2E2E2E] px-2 py-0.5 text-xs text-[#6B7280]">
                      {politician.uf}
                    </span>
                    <SeverityBadge severity={politician.maxSeverity} size="sm" />
                    <span className="text-xs text-[#6B7280]">
                      {politician.articleCount} {politician.articleCount === 1 ? "notícia" : "notícias"}
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
        {politicians.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <p className="text-sm text-[#6B7280]">Nenhum resultado encontrado.</p>
          </div>
        )}
      </div>

      {/* Desktop table (hidden below md) */}
      <div className="hidden md:block overflow-x-auto rounded-xl border border-[#2E2E2E]">
        <table className="w-full min-w-[640px]" aria-label="Ranking de candidatos">
          <thead>
            <tr className="border-b border-[#2E2E2E] bg-[#141414]">
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] w-12">#</th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] cursor-pointer hover:text-[#FAFAFA] transition-colors select-none"
                  onClick={() => handleSort(col.key)}
                  aria-label={`Ordenar por ${col.label}`}
                >
                  <span className="flex items-center gap-1">
                    {col.label}
                    {sortField === col.key ? (
                      <span className="text-emerald-400">
                        {sortOrder === "asc" ? "↑" : "↓"}
                      </span>
                    ) : (
                      <span className="text-[#3E3E3E]">↕</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1A1A1A]">
            {politicians.map((politician, index) => {
              const rowNum = (page - 1) * pageSize + index + 1;
              return (
                <tr
                  key={politician.id}
                  className="bg-[#0A0A0A] hover:bg-[#141414] transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-sm text-[#3E3E3E]">
                    {rowNum < 10 ? `0${rowNum}` : rowNum}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/politico/${politician.slug}`}
                      className="block min-w-0"
                    >
                      <p className="text-sm font-medium text-[#FAFAFA] hover:text-emerald-400 transition-colors truncate max-w-[200px]">
                        {politician.name}
                      </p>
                      <p className="text-xs text-[#6B7280] truncate max-w-[200px]">
                        {politician.role}
                      </p>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex items-center rounded px-2 py-0.5 text-xs font-bold text-white"
                      style={{ backgroundColor: politician.partyColor + "CC" }}
                    >
                      {politician.party}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-[#FAFAFA]">{politician.uf}</span>
                  </td>
                  <td className="px-4 py-3">
                    <ScoreBadge score={politician.score} size="sm" />
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-sm text-[#FAFAFA]">{politician.articleCount}</span>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={politician.maxSeverity} size="sm" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {politicians.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <p className="text-sm text-[#6B7280]">Nenhum resultado encontrado.</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1">
          <p className="text-xs text-[#6B7280]">
            <span className="hidden sm:inline">{total} políticos · </span>Página {page} de {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              aria-label="Página anterior"
              className="rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5 text-xs text-[#FAFAFA] hover:bg-[#1A1A1A] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Anterior
            </button>
            {(() => {
              const count = Math.min(5, totalPages);
              const startPage = Math.max(1, Math.min(page - 2, totalPages - count + 1));
              return Array.from({ length: count }, (_, i) => {
                const p = startPage + i;
                return (
                  <button
                    key={p}
                    onClick={() => onPageChange(p)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      p === page
                        ? "bg-emerald-500 text-white"
                        : "border border-[#2E2E2E] bg-[#141414] text-[#FAFAFA] hover:bg-[#1A1A1A]"
                    }`}
                  >
                    {p}
                  </button>
                );
              });
            })()}
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page === totalPages}
              aria-label="Próxima página"
              className="rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5 text-xs text-[#FAFAFA] hover:bg-[#1A1A1A] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RankingTable;
