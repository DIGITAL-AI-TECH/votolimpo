import { NextResponse } from "next/server";
import { ARTICLES } from "@/lib/mock-data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get("page") || "1");
  const pageSize = parseInt(searchParams.get("pageSize") || "20");
  const severity = searchParams.get("severity") || undefined;
  const politicianId = searchParams.get("politicianId") || undefined;

  let filtered = [...ARTICLES].sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  if (severity) filtered = filtered.filter((a) => a.severity === severity);
  if (politicianId) filtered = filtered.filter((a) => a.politicianIds.includes(politicianId));

  const total = filtered.length;
  const start = (page - 1) * pageSize;
  const data = filtered.slice(start, start + pageSize);

  return NextResponse.json({
    data,
    total,
    page,
    pageSize,
    totalPages: Math.ceil(total / pageSize),
  });
}
