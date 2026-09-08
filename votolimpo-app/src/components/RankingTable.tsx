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
  { key: "name", label: "Nome" },
  { key: "party", label: "Partido" },
  { key: "uf", label: "UF" },
  { key: "score", label: "Score" },
  { key: "articleCount", label: "Artigos" },
  { key: "maxSeverity", label: "Severidade" },
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
      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-[#2E2E2E]">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr className="border-b border-[#2E2E2E] bg-[#141414]">
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] w-12">#</th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] cursor-pointer hover:text-[#FAFAFA] transition-colors select-none"
                  onClick={() => handleSort(col.key)}
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
            {total} políticos · Página {page} de {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              className="rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-1.5 text-xs text-[#FAFAFA] hover:bg-[#1A1A1A] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Anterior
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2 + i, totalPages - 4 + i));
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
            })}
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page === totalPages}
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
