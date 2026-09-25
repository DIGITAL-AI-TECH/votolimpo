import type { Article, LegalMilestone, Severity } from "@/types";

export interface TimelineItem {
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
