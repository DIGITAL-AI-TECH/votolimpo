import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const areasRaw = await prisma.$queryRaw<
      Array<{ area: string; count: bigint; processed: bigint }>
    >`
      SELECT
        a.area,
        COUNT(*)::bigint as count,
        COUNT(ar.id)::bigint as processed
      FROM help_core.articles a
      LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
      GROUP BY a.area
      ORDER BY a.area ASC
    `;

    const areas = areasRaw.map((r: { area: string; count: bigint; processed: bigint }) => ({
      area: r.area,
      count: Number(r.count),
      processed: Number(r.processed),
    }));

    return NextResponse.json({ areas });
  } catch (error) {
    console.error("Areas error:", error);
    return NextResponse.json({ error: "Erro ao carregar áreas" }, { status: 500 });
  }
}
