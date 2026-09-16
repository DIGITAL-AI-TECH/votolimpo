"use client";

import { useState, useEffect, useCallback, type ChangeEvent } from "react";
import type { Politician, Article } from "@/types";
import PoliticianCard from "@/components/PoliticianCard";
import ArticleCard from "@/components/ArticleCard";

export default function BuscaPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<Politician[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const [isSearchMode, setIsSearchMode] = useState(false);

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
        setIsSearchMode(true);
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(debouncedQuery)}`
        );
        if (!res.ok) throw new Error("Search failed");
        const data = await res.json();
        setResults(data.politicians || []);
        setArticles(data.articles || []);
      } else {
        setIsSearchMode(false);
        setArticles([]);
        // Load initial list of candidates
        const res = await fetch("/api/politicians?pageSize=50");
        if (!res.ok) throw new Error("Fetch failed");
        const data = await res.json();
        setResults(data.data || []);
      }
    } catch (error) {
      console.error("Search error:", error);
      setResults([]);
      setArticles([]);
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

  const totalFound = results.length + (isSearchMode ? articles.length : 0);

  const getResultsLabel = () => {
    if (loading) return "Buscando...";
    if (!isSearchMode) {
      return results.length === 0
        ? "Nenhum resultado encontrado"
        : `${results.length} candidato${results.length !== 1 ? "s" : ""} encontrado${results.length !== 1 ? "s" : ""}`;
    }
    if (totalFound === 0) return "Nenhum resultado encontrado";
    const partes: string[] = [];
    if (results.length > 0) {
      partes.push(`${results.length} candidato${results.length !== 1 ? "s" : ""}`);
    }
    if (articles.length > 0) {
      partes.push(`${articles.length} artigo${articles.length !== 1 ? "s" : ""}`);
    }
    return `${partes.join(" e ")} encontrado${totalFound !== 1 ? "s" : ""}`;
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

      {/* Results summary */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-[#6B7280]">{getResultsLabel()}</p>
      </div>

      {loading && initialLoad ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        </div>
      ) : (
        <>
          {/* Candidates section */}
          {results.length > 0 ? (
            <section className="mb-10">
              {isSearchMode && articles.length > 0 && (
                <h2 className="mb-4 text-lg font-semibold text-[#FAFAFA]">Candidatos</h2>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {results.map((politician) => (
                  <PoliticianCard key={politician.id} politician={politician} />
                ))}
              </div>
            </section>
          ) : !isSearchMode ? (
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
          ) : null}

          {/* Articles section — only shown in search mode when there are articles */}
          {isSearchMode && articles.length > 0 && (
            <section>
              <h2 className="mb-4 text-lg font-semibold text-[#FAFAFA]">Artigos</h2>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {articles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            </section>
          )}

          {/* Empty state when search returns nothing at all */}
          {isSearchMode && results.length === 0 && articles.length === 0 && !loading && (
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
        </>
      )}
    </div>
  );
}
