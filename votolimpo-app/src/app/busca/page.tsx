"use client";

import { useState, useEffect, useCallback, type ChangeEvent } from "react";
import type { Politician } from "@/types";
import PoliticianCard from "@/components/PoliticianCard";

export default function BuscaPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<Politician[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Fetch results
  const fetchResults = useCallback(async () => {
    setLoading(true);
    try {
      if (debouncedQuery.trim()) {
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(debouncedQuery)}`
        );
        if (!res.ok) throw new Error("Search failed");
        const data = await res.json();
        setResults(data.politicians || []);
      } else {
        // Load initial list of candidates
        const res = await fetch("/api/politicians?pageSize=50");
        if (!res.ok) throw new Error("Fetch failed");
        const data = await res.json();
        setResults(data.data || []);
      }
    } catch (error) {
      console.error("Search error:", error);
      setResults([]);
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  }, [debouncedQuery]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const clearFilters = () => {
    setQuery("");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#FAFAFA]">Busca</h1>
        <p className="mt-2 text-[#6B7280]">
          Encontre candidatos por nome, partido ou estado
        </p>
      </div>

      {/* Search */}
      <div className="mb-8 space-y-4 rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
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
            placeholder="Buscar por nome, partido ou estado..."
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
      </div>

      {/* Results */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-[#6B7280]">
          {loading
            ? "Buscando..."
            : results.length === 0
            ? "Nenhum resultado encontrado"
            : `${results.length} candidato${results.length !== 1 ? "s" : ""} encontrado${results.length !== 1 ? "s" : ""}`}
        </p>
      </div>

      {loading && initialLoad ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        </div>
      ) : results.length > 0 ? (
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
            Tente termos diferentes
          </p>
          <button
            onClick={clearFilters}
            className="mt-6 rounded-lg bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            Limpar busca
          </button>
        </div>
      )}
    </div>
  );
}
