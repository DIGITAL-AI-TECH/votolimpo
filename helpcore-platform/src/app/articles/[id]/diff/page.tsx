import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { DiffViewer } from "@/components/DiffViewer";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export default async function DiffPage({ params }: Props) {
  const { id } = await params;
  const articleId = parseInt(id, 10);
  if (isNaN(articleId)) notFound();

  const article = await prisma.article.findUnique({
    where: { id: articleId },
    include: {
      analysis_results: {
        take: 1,
        orderBy: { processed_at: "desc" },
      },
    },
  });

  if (!article) notFound();

  const analysis = article.analysis_results[0];
  if (!analysis?.markdown_content) {
    return (
      <div className="p-6">
        <Link href={`/articles/${id}`} className="text-sm text-[#FF5722] hover:underline">
          ← Voltar ao artigo
        </Link>
        <Card className="mt-4">
          <div className="py-8 text-center text-[#9EA5AC]">
            <p className="text-lg font-semibold">Diff não disponível</p>
            <p className="mt-1 text-sm">
              Este artigo não possui conteúdo reescrito pelo LLM.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const original = article.content || "";
  const rewritten = analysis.markdown_content;
  const originalWords = original.split(/\s+/).filter(Boolean).length;
  const rewrittenWords = rewritten.split(/\s+/).filter(Boolean).length;
  const wordDiff = rewrittenWords - originalWords;

  return (
    <div className="p-6">
      <Link href={`/articles/${id}`} className="text-sm text-[#FF5722] hover:underline">
        ← Voltar ao artigo
      </Link>

      <div className="mt-4 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">{article.title}</h1>
          <p className="mt-1 text-sm text-[#9EA5AC]">
            Comparacao entre conteudo original e reescrita do LLM
          </p>
        </div>

        {/* Word count stats */}
        <Card>
          <div className="flex gap-8 text-sm">
            <div>
              <span className="text-[#9EA5AC]">Original</span>
              <p className="font-bold text-white">{originalWords.toLocaleString()} palavras</p>
            </div>
            <div>
              <span className="text-[#9EA5AC]">Reescrita</span>
              <p className="font-bold text-white">{rewrittenWords.toLocaleString()} palavras</p>
            </div>
            <div>
              <span className="text-[#9EA5AC]">Diferenca</span>
              <p className={`font-bold ${wordDiff >= 0 ? "text-green-400" : "text-red-400"}`}>
                {wordDiff >= 0 ? "+" : ""}{wordDiff.toLocaleString()} palavras
              </p>
            </div>
          </div>
        </Card>

        {/* Diff viewer */}
        <Card>
          <CardHeader>
            <CardTitle>Diff Visual</CardTitle>
          </CardHeader>
          <DiffViewer oldValue={original} newValue={rewritten} />
        </Card>
      </div>
    </div>
  );
}
