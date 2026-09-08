import type { FC } from "react";
import type { Article } from "@/types";
import SeverityBadge from "./SeverityBadge";

interface ArticleCardProps {
  article: Article;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getTruthScoreColor(score: number): string {
  if (score >= 0.9) return "text-emerald-400";
  if (score >= 0.75) return "text-blue-400";
  if (score >= 0.6) return "text-yellow-400";
  return "text-red-400";
}

const ArticleCard: FC<ArticleCardProps> = ({ article }) => {
  return (
    <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 transition-all duration-200 hover:border-[#3E3E3E] hover:bg-[#1A1A1A]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-2">
            <SeverityBadge severity={article.severity} size="sm" />
            <span className="text-xs text-[#6B7280]">{article.source.name}</span>
            <span className="text-xs text-[#6B7280]">·</span>
            <span className="text-xs text-[#6B7280]">{formatDate(article.publishedAt)}</span>
          </div>

          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm font-semibold text-[#FAFAFA] hover:text-emerald-400 transition-colors leading-snug mb-2"
          >
            {article.title}
          </a>

          <p className="text-xs text-[#6B7280] line-clamp-2 leading-relaxed">
            {article.summary}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="flex flex-wrap gap-1.5">
          {article.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded bg-[#2E2E2E] px-1.5 py-0.5 text-xs text-[#6B7280]"
            >
              #{tag}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <span className="text-xs text-[#6B7280]">Veracidade:</span>
          <span className={`font-mono text-xs font-bold ${getTruthScoreColor(article.truthScore)}`}>
            {Math.round(article.truthScore * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
};

export default ArticleCard;
