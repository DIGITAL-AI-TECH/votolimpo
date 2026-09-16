import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Como Funciona",
  description:
    "Entenda como o Voto Limpo coleta, processa e analisa dados publicos para gerar indices de transparencia dos politicos brasileiros.",
  alternates: {
    canonical: "https://votolimpo.com.br/como-funciona",
  },
  openGraph: {
    title: "Como Funciona | Voto Limpo",
    description:
      "Entenda como o Voto Limpo coleta e analisa dados publicos para gerar indices de transparencia.",
    url: "https://votolimpo.com.br/como-funciona",
  },
};

export default function ComoFuncionaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
