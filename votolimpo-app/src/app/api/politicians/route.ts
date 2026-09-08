import { NextResponse } from "next/server";
import { POLITICIANS } from "@/lib/mock-data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get("page") || "1");
  const pageSize = parseInt(searchParams.get("pageSize") || "20");
  const party = searchParams.get("party") || undefined;
  const uf = searchParams.get("uf") || undefined;

  let filtered = [...POLITICIANS];

  if (party) filtered = filtered.filter((p) => p.party === party);
  if (uf) filtered = filtered.filter((p) => p.uf === uf);

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
