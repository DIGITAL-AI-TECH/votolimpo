import type { FC } from "react";
import type { Article, LegalMilestone, Severity } from "@/types";
import SeverityBadge from "./SeverityBadge";

interface TimelineItem {
  id: string;
  type: "article" | "milestone";
  date: string;
  title: string;
  description: string;
  severity: Severity;
  url?: string;
  source?: string;
  court?: string;
  milestoneType?: string;
}

interface TimelineProps {
  items: TimelineItem[];
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

const MILESTONE_ICONS: Record<string, JSX.Element> = {
  indictment: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ),
  conviction: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
    </svg>
  ),
  acquittal: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  investigation: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  ),
  impeachment: (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  ),
};

function getMilestoneTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    indictment: "Indiciamento",
    conviction: "Condenação",
    acquittal: "Absolvição",
    investigation: "Investigação",
    appeal: "Recurso",
    settlement: "Acordo",
    impeachment: "Impeachment",
    election: "Eleição",
  };
  return labels[type] || type;
}

const TimelineItemComponent: FC<{ item: TimelineItem }> = ({ item }) => {
  const isArticle = item.type === "article";

  return (
    <div className="relative flex gap-4 pb-6 last:pb-0">
      {/* Vertical line */}
      <div className="absolute left-5 top-10 bottom-0 w-px bg-[#2E2E2E] last:hidden" />

      {/* Icon */}
      <div
        className={`relative z-10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border-2 ${
          isArticle
            ? "border-[#2E2E2E] bg-[#141414] text-[#6B7280]"
            : item.severity === "critical"
            ? "border-red-500/50 bg-red-500/10 text-red-400"
            : item.severity === "high"
            ? "border-orange-500/50 bg-orange-500/10 text-orange-400"
            : "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
        }`}
      >
        {isArticle ? (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
          </svg>
        ) : (
          MILESTONE_ICONS[item.milestoneType || "investigation"] || MILESTONE_ICONS.investigation
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 hover:border-[#3E3E3E] transition-colors">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            {!isArticle && (
              <span className="rounded bg-[#242424] px-2 py-0.5 text-xs font-medium text-[#FAFAFA]">
                {getMilestoneTypeLabel(item.milestoneType || "")}
              </span>
            )}
            <SeverityBadge severity={item.severity} size="sm" />
            <span className="text-xs text-[#6B7280]">{formatDate(item.date)}</span>
            {item.source && (
              <>
                <span className="text-xs text-[#3E3E3E]">·</span>
                <span className="text-xs text-[#6B7280]">{item.source}</span>
              </>
            )}
            {item.court && (
              <>
                <span className="text-xs text-[#3E3E3E]">·</span>
                <span className="text-xs text-[#6B7280]">{item.court}</span>
              </>
            )}
          </div>

          <h3 className="text-sm font-semibold text-[#FAFAFA] mb-1.5 leading-snug">
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-emerald-400 transition-colors"
              >
                {item.title}
              </a>
            ) : (
              item.title
            )}
          </h3>

          <p className="text-xs text-[#6B7280] leading-relaxed line-clamp-3">
            {item.description}
          </p>
        </div>
      </div>
    </div>
  );
};

export function buildTimelineItems(
  articles: Article[],
  milestones: LegalMilestone[]
): TimelineItem[] {
  const articleItems: TimelineItem[] = articles.map((a) => ({
    id: a.id,
    type: "article",
    date: a.publishedAt,
    title: a.title,
    description: a.summary,
    severity: a.severity,
    url: a.url,
    source: a.source.name,
  }));

  const milestoneItems: TimelineItem[] = milestones.map((m) => ({
    id: m.id,
    type: "milestone",
    date: m.date,
    title: m.title,
    description: m.description,
    severity: m.severity,
    court: m.court,
    milestoneType: m.type,
  }));

  return [...articleItems, ...milestoneItems].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );
}

const Timeline: FC<TimelineProps> = ({ items }) => {
  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-[#6B7280]">Nenhum item na timeline.</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {items.map((item) => (
        <TimelineItemComponent key={item.id} item={item} />
      ))}
    </div>
  );
};

export default Timeline;
