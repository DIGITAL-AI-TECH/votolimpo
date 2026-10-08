import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { ScoreBadge } from "@/components/ScoreBadge";

interface ArticleCardProps {
  id: number;
  title: string;
  area: string;
  lista?: string | null;
  classification?: string | null;
  modifiedDate?: string | null;
  isProcessed: boolean;
  overallScore?: number | null;
  priorityLevel?: string | null;
  highlight?: string;
}

export function ArticleCard({
  id,
  title,
  area,
  lista,
  classification,
  modifiedDate,
  isProcessed,
  overallScore,
  priorityLevel,
  highlight,
}: ArticleCardProps) {
  return (
    <Link
      href={`/articles/${id}`}
      className="block rounded-2xl border border-[#1F1F1F] bg-[#151515] p-4 transition-all hover:border-[#FF5722]/30 hover:shadow-[0_10px_30px_rgba(255,87,34,0.1)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-white truncate">{title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[#9EA5AC]">
            <span>{area}</span>
            {lista && (
              <>
                <span>·</span>
                <span>{lista}</span>
              </>
            )}
            {modifiedDate && (
              <>
                <span>·</span>
                <span>{new Date(modifiedDate).toLocaleDateString("pt-BR")}</span>
              </>
            )}
          </div>
          {highlight && (
            <p
              className="mt-2 text-sm text-[#9EA5AC] line-clamp-2"
              dangerouslySetInnerHTML={{ __html: highlight }}
            />
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {classification && (
            <Badge>{classification}</Badge>
          )}
          {isProcessed ? (
            <ScoreBadge priority={priorityLevel || null} score={overallScore} />
          ) : (
            <Badge>Pendente</Badge>
          )}
        </div>
      </div>
    </Link>
  );
}
