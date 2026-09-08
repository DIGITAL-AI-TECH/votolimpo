import { NextResponse } from "next/server";
import { searchPoliticians, ARTICLES } from "@/lib/mock-data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q") || "";

  if (!q.trim()) {
    return NextResponse.json({
      politicians: [],
      articles: [],
      total: 0,
    });
  }

  const politicians = searchPoliticians(q);
  const ql = q.toLowerCase();
  const articles = ARTICLES.filter(
    (a) =>
      a.title.toLowerCase().includes(ql) ||
      a.summary.toLowerCase().includes(ql) ||
      a.tags.some((t) => t.toLowerCase().includes(ql))
  ).slice(0, 10);

  return NextResponse.json({
    politicians,
    articles,
    total: politicians.length + articles.length,
  });
}
