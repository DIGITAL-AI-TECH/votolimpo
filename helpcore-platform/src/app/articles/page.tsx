"use client";

import { useState, useEffect, useCallback } from "react";
import { AREAS, PRIORITY_LEVELS } from "@/lib/constants";
import { ArticleCard } from "@/components/ArticleCard";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface ArticleResult {
  id: number;
  title: string;
  area: string;
  lista: string | null;
  classification: string | null;
  modified_date: string | null;
  is_processed: boolean;
  overall_score: number | null;
  priority_level: string | null;
  highlight: string;
}

interface Pagination {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export default function ArticlesSearchPage() {
  const [search, setSearch] = useState("");
  const [area, setArea] = useState("");
  const [priority, setPriority] = useState("");
  const [docType, setDocType] = useState("");
  const [scoreMin, setScoreMin] = useState("");
  const [scoreMax, setScoreMax] = useState("");
  const [articles, setArticles] = useState<ArticleResult[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasSearched, setHasSearched] = useState(false);

  const fetchArticles = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (area) params.set("area", area);
      if (priority) params.set("priority", priority);
      if (docType) params.set("doc_type", docType);
      if (scoreMin) params.set("score_min", scoreMin);
      if (scoreMax) params.set("score_max", scoreMax);
      params.set("page", String(p));
      params.set("per_page", "30");

      const res = await fetch(`/api/articles?${params}`);
      const data = await res.json();
      setArticles(data.articles || []);
      setPagination(data.pagination || null);
      setHasSearched(true);
    } finally {
      setLoading(false);
    }
  }, [search, area, priority, docType, scoreMin, scoreMax]);

  useEffect(() => {
    if (hasSearched) {
      fetchArticles(page);
    }
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchArticles(1);
  };

  const clearFilters = () => {
    setSearch("");
    setArea("");
    setPriority("");
    setDocType("");
    setScoreMin("");
    setScoreMax("");
    setPage(1);
    setArticles([]);
    setPagination(null);
    setHasSearched(false);
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Buscar Artigos</h1>

      {/* Filter Panel */}
      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
        </CardHeader>
        <form onSubmit={handleSearch} className="space-y-4">
          {/* Search input */}
          <Input
            placeholder="Buscar por texto (ex: cartão crédito, pix, seguro)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          {/* Filter row */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {/* Area */}
            <select
              value={area}
              onChange={(e) => setArea(e.target.value)}
              className="rounded-xl border border-[#1F1F1F] bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#FF5722] focus:outline-none focus:ring-1 focus:ring-[#FF5722]"
            >
              <option value="">Todas as áreas</option>
              {AREAS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>

            {/* Priority */}
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="rounded-xl border border-[#1F1F1F] bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#FF5722] focus:outline-none focus:ring-1 focus:ring-[#FF5722]"
            >
              <option value="">Todas prioridades</option>
              {PRIORITY_LEVELS.map((p) => (
                <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
              ))}
            </select>

            {/* Doc type */}
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="rounded-xl border border-[#1F1F1F] bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#FF5722] focus:outline-none focus:ring-1 focus:ring-[#FF5722]"
            >
              <option value="">Todos os tipos</option>
              <option value="procedimento">Procedimento</option>
              <option value="politica">Política</option>
              <option value="faq">FAQ</option>
              <option value="guia">Guia</option>
              <option value="referencia">Referência</option>
              <option value="formulario">Formulário</option>
            </select>

            {/* Score range */}
            <div className="flex gap-2">
              <Input
                type="number"
                min="0"
                max="100"
                placeholder="Score min"
                value={scoreMin}
                onChange={(e) => setScoreMin(e.target.value)}
                className="w-1/2"
              />
              <Input
                type="number"
                min="0"
                max="100"
                placeholder="Score max"
                value={scoreMax}
                onChange={(e) => setScoreMax(e.target.value)}
                className="w-1/2"
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <Button type="submit" disabled={loading}>
              {loading ? "Buscando..." : "Buscar"}
            </Button>
            <Button type="button" variant="outline" onClick={clearFilters}>
              Limpar
            </Button>
          </div>
        </form>
      </Card>

      {/* Results */}
      {hasSearched && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[#9EA5AC]">
              {pagination ? `${pagination.total.toLocaleString()} resultado(s)` : ""}
            </p>
          </div>

          {articles.length === 0 ? (
            <Card>
              <div className="py-8 text-center text-[#9EA5AC]">
                <p className="text-lg font-semibold">Nenhum artigo encontrado</p>
                <p className="mt-1 text-sm">Tente ajustar os filtros ou termos de busca.</p>
              </div>
            </Card>
          ) : (
            <>
              <div className="space-y-3">
                {articles.map((article) => (
                  <ArticleCard
                    key={article.id}
                    id={article.id}
                    title={article.title}
                    area={article.area}
                    lista={article.lista}
                    classification={article.classification}
                    modifiedDate={article.modified_date}
                    isProcessed={article.is_processed}
                    overallScore={article.overall_score}
                    priorityLevel={article.priority_level}
                    highlight={article.highlight}
                  />
                ))}
              </div>

              {/* Pagination */}
              {pagination && pagination.total_pages > 1 && (
                <div className="flex items-center justify-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Anterior
                  </Button>
                  <span className="text-sm text-[#9EA5AC]">
                    Página {page} de {pagination.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= pagination.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Próxima
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
