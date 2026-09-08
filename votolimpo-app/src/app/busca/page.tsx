"use client";

import { useState, useEffect, useCallback, type ChangeEvent } from "react";
import type { Politician } from "@/types";
import {
  POLITICIANS,
  searchPoliticians,
  getPartiesList,
  getUFList,
} from "@/lib/mock-data";
import PoliticianCard from "@/components/PoliticianCard";

const SEVERITY_OPTIONS = [
  { value: "critical", label: "Crítico" },
  { value: "high", label: "Alto" },
  { value: "medium", label: "Médio" },
  { value: "low", label: "Baixo" },
  { value: "info", label: "Info" },
];

export default function BuscaPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedParty, setSelectedParty] = useState("");
  const [selectedUF, setSelectedUF] = useState("");
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
  const [results, setResults] = useState<Politician[]>(POLITICIANS);

  const parties = getPartiesList();
  const ufs = getUFList();

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Apply filters
  const applyFilters = useCallback(() => {
    let filtered = debouncedQuery ? searchPoliticians(debouncedQuery) : [...POLITICIANS];

    if (selectedParty) {
      filtered = filtered.filter((p) => p.party === selectedParty);
    }

    if (selectedUF) {
      filtered = filtered.filter((p) => p.uf === selectedUF);
    }

    if (selectedSeverities.length > 0) {
      filtered = filtered.filter((p) =>
        selectedSeverities.includes(p.maxSeverity)
      );
    }

    setResults(filtered);
  }, [debouncedQuery, selectedParty, selectedUF, selectedSeverities]);

  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  const toggleSeverity = (severity: string) => {
    setSelectedSeverities((prev) =>
      prev.includes(severity)
        ? prev.filter((s) => s !== severity)
        : [...prev, severity]
    );
  };

  const clearFilters = () => {
    setQuery("");
    setSelectedParty("");
    setSelectedUF("");
    setSelectedSeverities([]);
  };

  const hasFilters = query || selectedParty || selectedUF || selectedSeverities.length > 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#FAFAFA]">Busca</h1>
        <p className="mt-2 text-[#6B7280]">
          Encontre políticos por nome, partido, estado ou histórico
        </p>
      </div>

      {/* Search & Filters */}
      <div className="mb-8 space-y-4 rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
        {/* Search input */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B7280]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
            placeholder="Buscar por nome, partido, UF ou cargo..."
            className="w-full rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] py-2.5 pl-10 pr-4 text-sm text-[#FAFAFA] placeholder-[#6B7280] outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#FAFAFA]"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Filter row */}
        <div className="flex flex-wrap gap-3">
          {/* Party filter */}
          <select
            value={selectedParty}
            onChange={(e) => setSelectedParty(e.target.value)}
            className="rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-500/50"
          >
            <option value="">Todos os partidos</option>
            {parties.map((party) => (
              <option key={party} value={party}>{party}</option>
            ))}
          </select>

          {/* UF filter */}
          <select
            value={selectedUF}
            onChange={(e) => setSelectedUF(e.target.value)}
            className="rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-500/50"
          >
            <option value="">Todos os estados</option>
            {ufs.map((uf) => (
              <option key={uf} value={uf}>{uf}</option>
            ))}
          </select>

          {/* Severity filter */}
          <div className="flex flex-wrap gap-2">
            {SEVERITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => toggleSeverity(opt.value)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  selectedSeverities.includes(opt.value)
                    ? opt.value === "critical"
                      ? "border-red-400 bg-red-400/20 text-red-400"
                      : opt.value === "high"
                      ? "border-orange-400 bg-orange-400/20 text-orange-400"
                      : opt.value === "medium"
                      ? "border-yellow-400 bg-yellow-400/20 text-yellow-400"
                      : opt.value === "low"
                      ? "border-blue-400 bg-blue-400/20 text-blue-400"
                      : "border-gray-400 bg-gray-400/20 text-gray-400"
                    : "border-[#2E2E2E] text-[#6B7280] hover:border-[#3E3E3E] hover:text-[#FAFAFA]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="rounded-lg px-3 py-2 text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors"
            >
              Limpar filtros
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-[#6B7280]">
          {results.length === 0
            ? "Nenhum resultado encontrado"
            : `${results.length} político${results.length !== 1 ? "s" : ""} encontrado${results.length !== 1 ? "s" : ""}`}
        </p>
      </div>

      {results.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {results.map((politician) => (
            <PoliticianCard key={politician.id} politician={politician} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[#2E2E2E] bg-[#141414]">
            <svg className="h-8 w-8 text-[#3E3E3E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-[#FAFAFA]">Nenhum resultado</h3>
          <p className="mt-2 text-sm text-[#6B7280]">
            Tente termos diferentes ou remova alguns filtros
          </p>
          <button
            onClick={clearFilters}
            className="mt-6 rounded-lg bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            Limpar filtros
          </button>
        </div>
      )}
    </div>
  );
}
