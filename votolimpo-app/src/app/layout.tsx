import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { getGlobalStats, ncStatsToStats } from "@/lib/nc-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL("https://votolimpo.com.br"),
  title: {
    default: "Voto Limpo — Transparencia Politica",
    template: "%s | Voto Limpo",
  },
  description:
    "Plataforma de transparencia politica brasileira. Acompanhe o historico, vinculos e indice de transparencia dos politicos do Brasil.",
  keywords: [
    "transparencia",
    "politica",
    "Brasil",
    "corrupcao",
    "eleicoes",
    "democracia",
    "candidatos",
    "vereador",
    "deputado",
    "senador",
    "governador",
    "presidente",
  ],
  authors: [{ name: "Voto Limpo", url: "https://votolimpo.com.br" }],
  creator: "Voto Limpo",
  publisher: "Voto Limpo",
  alternates: {
    canonical: "https://votolimpo.com.br",
  },
  openGraph: {
    type: "website",
    locale: "pt_BR",
    url: "https://votolimpo.com.br",
    siteName: "Voto Limpo",
    title: "Voto Limpo — Transparencia Politica",
    description:
      "Acompanhe o historico e vinculos dos politicos brasileiros com transparencia e dados verificados.",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Voto Limpo — Transparencia Politica Brasileira",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@votolimpo",
    creator: "@votolimpo",
    title: "Voto Limpo — Transparencia Politica",
    description: "Acompanhe o historico e vinculos dos politicos brasileiros.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  category: "politics",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  let stats;
  try {
    const ncStats = await getGlobalStats();
    stats = ncStatsToStats(ncStats);
  } catch {
    // Fallback stats if NC API is unavailable
    stats = {
      totalPoliticians: 0,
      totalArticles: 0,
      totalEntities: 0,
      totalRelationships: 0,
      avgScore: 0,
      criticalCount: 0,
    };
  }

  return (
    <html lang="pt-BR" className="dark">
      <body className="min-h-screen bg-[#0A0A0A] text-[#FAFAFA] flex flex-col antialiased">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer stats={stats} />
      </body>
    </html>
  );
}
