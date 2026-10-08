import Link from "next/link";
import { prisma } from "@/lib/db";
import { Card } from "@/components/ui/Card";

export const dynamic = "force-dynamic";

async function getAreas() {
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

  return areasRaw.map((r: { area: string; count: bigint; processed: bigint }) => ({
    area: r.area as string,
    count: Number(r.count),
    processed: Number(r.processed),
  }));
}

export default async function BrowsePage() {
  const areas = await getAreas();
  const totalArticles = areas.reduce((sum: number, a: { count: number }) => sum + a.count, 0);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white">Help Browser</h1>
      <p className="mt-1 text-sm text-[#9EA5AC]">
        {totalArticles.toLocaleString("pt-BR")} artigos em {areas.length} áreas operacionais
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {areas.map((a: { area: string; count: number; processed: number }) => {
          const pct = a.count > 0 ? Math.round((a.processed / a.count) * 100) : 0;
          return (
            <Link key={a.area} href={`/browse/${encodeURIComponent(a.area)}`}>
              <Card className="transition-all hover:border-[#FF5722]/30 hover:shadow-[0_10px_30px_rgba(255,87,34,0.1)]">
                <h3 className="font-bold text-white">{a.area}</h3>
                <div className="mt-2 flex items-center justify-between text-sm">
                  <span className="text-[#9EA5AC]">
                    {a.count.toLocaleString("pt-BR")} artigos
                  </span>
                  <span className="font-semibold text-[#FF5722]">{pct}%</span>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[#1A1A1A]">
                  <div
                    className="h-full rounded-full bg-[#FF5722]"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
