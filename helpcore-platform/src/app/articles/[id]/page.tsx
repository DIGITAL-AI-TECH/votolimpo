import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ScoreBadge } from "@/components/ScoreBadge";
import { QualityRadar } from "@/components/QualityRadar";
import { StepsChecklist } from "@/components/StepsChecklist";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export default async function ArticleDetailPage({ params }: Props) {
  const { id } = await params;
  const articleId = parseInt(id, 10);
  if (isNaN(articleId)) notFound();

  const article = await prisma.article.findUnique({
    where: { id: articleId },
    include: {
      analysis_results: {
        take: 1,
        orderBy: { processed_at: "desc" },
        include: {
          review_actions: {
            take: 1,
            orderBy: { created_at: "desc" },
          },
        },
      },
    },
  });

  if (!article) notFound();

  const analysis = article.analysis_results[0] || null;

  return (
    <div className="p-6">
      <Link href="/browse" className="text-sm text-[#FF5722] hover:underline">
        ← Voltar
      </Link>

      <div className="mt-4 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">{article.title}</h1>
          {article.subtitle && (
            <p className="mt-1 text-[#D4D8DD]">{article.subtitle}</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[#9EA5AC]">
            <Badge>{article.area}</Badge>
            {article.lista && <Badge variant="default">{article.lista}</Badge>}
            {article.classification && (
              <Badge variant="default">{article.classification}</Badge>
            )}
            {article.modified_date && (
              <span>
                Modificado: {new Date(article.modified_date).toLocaleDateString("pt-BR")}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <Card>
          <CardHeader>
            <CardTitle>Conteúdo Original</CardTitle>
          </CardHeader>
          <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm text-[#D4D8DD]">
            {article.content || (
              <p className="italic text-[#9EA5AC]">Sem conteúdo disponível.</p>
            )}
          </div>
        </Card>

        {/* Links */}
        {article.links && article.links.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Links Internos ({article.links.length})</CardTitle>
            </CardHeader>
            <ul className="space-y-1 text-sm">
              {article.links.map((link: string, i: number) => (
                <li key={i} className="text-[#FF8A65] break-all">{link}</li>
              ))}
            </ul>
          </Card>
        )}

        {/* Analysis Results */}
        {analysis ? (
          <>
            {/* Inventory */}
            <Card>
              <CardHeader>
                <CardTitle>Inventário</CardTitle>
              </CardHeader>
              <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-3">
                {[
                  ["Tipo", analysis.doc_type],
                  ["Categoria", analysis.category],
                  ["Subcategoria", analysis.subcategory],
                  ["Público-alvo", analysis.target_audience],
                  ["Área (LLM)", analysis.area_operacional],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <span className="text-[#9EA5AC]">{label}</span>
                    <p className="font-medium text-white">{(value as string) || "—"}</p>
                  </div>
                ))}
                {analysis.key_topics && (
                  <div className="col-span-full">
                    <span className="text-[#9EA5AC]">Tópicos-chave</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {(analysis.key_topics as string[]).map((t, i) => (
                        <Badge key={i}>{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Quality */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Qualidade</CardTitle>
                  <ScoreBadge
                    priority={analysis.priority_level}
                    score={analysis.overall_score ? Number(analysis.overall_score) : null}
                  />
                </div>
              </CardHeader>
              <QualityRadar
                clarity={analysis.clarity ? Number(analysis.clarity) : null}
                structure={analysis.structure ? Number(analysis.structure) : null}
                completeness={analysis.completeness ? Number(analysis.completeness) : null}
                accuracy_signals={analysis.accuracy_signals ? Number(analysis.accuracy_signals) : null}
                readability={analysis.readability ? Number(analysis.readability) : null}
                overall_score={analysis.overall_score ? Number(analysis.overall_score) : null}
              />
            </Card>

            {/* Steps */}
            {analysis.steps && (analysis.steps as Array<Record<string, string>>).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Passos Extraidos</CardTitle>
                </CardHeader>
                <StepsChecklist
                  steps={analysis.steps as Array<{ order?: number; action: string; detail?: string }>}
                />
              </Card>
            )}

            {/* Suggestions */}
            {analysis.improvement_suggestions &&
              (analysis.improvement_suggestions as string[]).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Sugestões de Melhoria</CardTitle>
                  </CardHeader>
                  <ul className="space-y-2 text-sm">
                    {(analysis.improvement_suggestions as string[]).map((s, i) => (
                      <li key={i} className="flex gap-2 text-[#D4D8DD]">
                        <span className="text-[#FFC978]">→</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

            {/* Diff link */}
            {analysis.markdown_content && (
              <div className="flex gap-3">
                <Link
                  href={`/articles/${article.id}/diff`}
                  className="inline-flex items-center gap-2 rounded-xl border border-[#FF5722] px-4 py-2 text-sm font-semibold text-[#FF5722] transition-colors hover:bg-[#FF5722] hover:text-white"
                >
                  Ver Diff Visual
                </Link>
              </div>
            )}
          </>
        ) : (
          <Card>
            <div className="py-8 text-center text-[#9EA5AC]">
              <p className="text-lg font-semibold">Aguardando processamento</p>
              <p className="mt-1 text-sm">
                Este artigo ainda não foi analisado pelo LLM.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
