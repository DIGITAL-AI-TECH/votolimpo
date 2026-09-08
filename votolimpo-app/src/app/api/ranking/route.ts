import { NextResponse } from "next/server";
import { getRanking } from "@/lib/mock-data";
import type { SortField, SortOrder } from "@/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const party = searchParams.get("party") || undefined;
  const uf = searchParams.get("uf") || undefined;
  const page = parseInt(searchParams.get("page") || "1");
  const pageSize = parseInt(searchParams.get("pageSize") || "20");
  const sortBy = (searchParams.get("sortBy") || "score") as SortField;
  const sortOrder = (searchParams.get("sortOrder") || "asc") as SortOrder;

  const { data, total } = getRanking(party, uf, page, pageSize, sortBy, sortOrder);

  return NextResponse.json({
    data,
    total,
    page,
    pageSize,
    totalPages: Math.ceil(total / pageSize),
  });
}
