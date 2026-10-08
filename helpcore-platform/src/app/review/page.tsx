"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import Link from "next/link";

interface ReviewArticle {
  id: number;
  title: string;
  area: string;
  overall_score: number | null;
  priority_level: string | null;
  analysis_id: number;
  review_status: string | null;
}

export default function ReviewQueuePage() {
  const [articles, setArticles] = useState<ReviewArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [filter, setFilter] = useState<"pending" | "all">("pending");

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/review?filter=${filter}`);
      const data = await res.json();
      setArticles(data.articles || []);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const submitReview = async (articleId: number, analysisId: number, action: string) => {
    if (action !== "approved" && !notes.trim()) {
      alert("Notas são obrigatórias para rejeição ou revisão.");
      return;
    }

    try {
      const res = await fetch(`/api/articles/${articleId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, notes: notes.trim() || undefined }),
      });

      if (res.ok) {
        setReviewingId(null);
        setNotes("");
        fetchQueue();
      } else {
        const data = await res.json();
        alert(data.error || "Erro ao salvar revisão");
      }
    } catch {
      alert("Erro de conexão");
    }
  };

  const priorityVariant = (p: string | null) => {
    if (p === "critical") return "critical" as const;
    if (p === "high") return "high" as const;
    if (p === "medium") return "medium" as const;
    return "low" as const;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Fila de Revisão</h1>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={filter === "pending" ? "primary" : "outline"}
            onClick={() => setFilter("pending")}
          >
            Pendentes
          </Button>
          <Button
            size="sm"
            variant={filter === "all" ? "primary" : "outline"}
            onClick={() => setFilter("all")}
          >
            Todos
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <div className="h-16 animate-pulse rounded bg-[#1A1A1A]" />
            </Card>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <Card>
          <div className="py-8 text-center text-[#9EA5AC]">
            <p className="text-lg font-semibold">
              {filter === "pending" ? "Nenhum artigo pendente de revisão" : "Nenhum artigo processado"}
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {articles.map((article) => (
            <Card key={article.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/articles/${article.id}`}
                    className="text-white font-medium hover:text-[#FF5722] transition-colors"
                  >
                    {article.title}
                  </Link>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge>{article.area}</Badge>
                    {article.priority_level && (
                      <Badge variant={priorityVariant(article.priority_level)}>
                        {article.priority_level}
                      </Badge>
                    )}
                    {article.overall_score != null && (
                      <span className="text-xs text-[#9EA5AC]">
                        Score: {Number(article.overall_score).toFixed(0)}
                      </span>
                    )}
                    {article.review_status && (
                      <Badge
                        variant={
                          article.review_status === "approved"
                            ? "low"
                            : article.review_status === "rejected"
                              ? "critical"
                              : "medium"
                        }
                      >
                        {article.review_status}
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Review actions */}
                {!article.review_status && (
                  <div className="flex shrink-0 gap-2">
                    {reviewingId === article.id ? (
                      <div className="flex flex-col gap-2">
                        <textarea
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                          placeholder="Notas (obrigatório para rejeição)..."
                          className="h-20 w-64 rounded-lg border border-[#1F1F1F] bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-[#9EA5AC] focus:border-[#FF5722] focus:outline-none"
                        />
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => submitReview(article.id, article.analysis_id, "approved")}
                          >
                            Aprovar
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => submitReview(article.id, article.analysis_id, "rejected")}
                          >
                            Rejeitar
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => { setReviewingId(null); setNotes(""); }}
                          >
                            Cancelar
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setReviewingId(article.id)}
                      >
                        Revisar
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
