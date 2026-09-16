import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Busca",
  description:
    "Busque candidatos por nome, partido ou estado. Encontre artigos e informacoes sobre politicos brasileiros.",
  alternates: {
    canonical: "https://votolimpo.com.br/busca",
  },
  openGraph: {
    title: "Busca | Voto Limpo",
    description:
      "Busque candidatos por nome, partido ou estado no Voto Limpo.",
    url: "https://votolimpo.com.br/busca",
  },
};

export default function BuscaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
