import { prisma } from "@/lib/db";
import { ArticleCard } from "@/components/ArticleCard";
import { Button } from "@/components/ui/Button";
import Link from "next/link";
import { PAGINATION } from "@/lib/constants";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ area: string }>;
  searchParams: Promise<{ page?: string }>;
}

export default async function AreaPage({ params, searchParams }: Props) {
  const { area: encodedArea } = await params;
  const { page: pageStr } = await searchParams;
  const area = decodeURIComponent(encodedArea);
  const page = Math.max(1, parseInt(pageStr || "1", 10));
  const perPage = PAGINATION.DEFAULT_PER_PAGE;
  const offset = (page - 1) * perPage;

  const [articles, countResult] = await Promise.all([
    prisma.$queryRaw<Array<Record<string, unknown>>>`
      SELECT
        a.id, a.title, a.area, a.lista, a.classification, a.modified_date,
        CASE WHEN ar.id IS NOT NULL THEN true ELSE false END as is_processed,
        ar.overall_score,
        ar.priority_level
      FROM help_core.articles a
      LEFT JOIN help_core.analysis_results ar ON ar.article_id = a.id
      WHERE a.area = ${area}
      ORDER BY a.title ASC
      LIMIT ${perPage} OFFSET ${offset}
    `,
    prisma.$queryRaw<Array<{ count: bigint }>>`
      SELECT COUNT(*)::bigint as count FROM help_core.articles WHERE area = ${area}
    `,
  ]);

  const total = Number(countResult[0]?.count || 0);
  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="p-6">
      <div className="mb-6">
        <Link href="/browse" className="text-sm text-[#FF5722] hover:underline">
          ← Voltar para áreas
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-white">{area}</h1>
        <p className="text-sm text-[#9EA5AC]">
          {total.toLocaleString("pt-BR")} artigos
        </p>
      </div>

      <div className="space-y-3">
        {articles.map((a: Record<string, unknown>) => (
          <ArticleCard
            key={Number(a.id)}
            id={Number(a.id)}
            title={a.title as string}
            area={a.area as string}
            lista={a.lista as string | null}
            classification={a.classification as string | null}
            modifiedDate={a.modified_date ? String(a.modified_date) : null}
            isProcessed={Boolean(a.is_processed)}
            overallScore={a.overall_score ? Number(a.overall_score) : null}
            priorityLevel={a.priority_level as string | null}
          />
        ))}

        {articles.length === 0 && (
          <p className="py-12 text-center text-[#9EA5AC]">
            Nenhum artigo encontrado nesta área.
          </p>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          {page > 1 && (
            <Link href={`/browse/${encodeURIComponent(area)}?page=${page - 1}`}>
              <Button variant="outline" size="sm">Anterior</Button>
            </Link>
          )}
          <span className="text-sm text-[#9EA5AC]">
            Página {page} de {totalPages}
          </span>
          {page < totalPages && (
            <Link href={`/browse/${encodeURIComponent(area)}?page=${page + 1}`}>
              <Button variant="outline" size="sm">Próxima</Button>
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
