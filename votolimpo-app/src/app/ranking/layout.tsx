import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ranking de Candidatos",
  description:
    "Ranking de transparencia dos candidatos brasileiros. Compare indices, partidos e estados em uma visao consolidada.",
  alternates: {
    canonical: "https://votolimpo.com.br/ranking",
  },
  openGraph: {
    title: "Ranking de Candidatos | Voto Limpo",
    description:
      "Ranking de transparencia dos candidatos brasileiros. Compare indices, partidos e estados.",
    url: "https://votolimpo.com.br/ranking",
  },
};

export default function RankingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
