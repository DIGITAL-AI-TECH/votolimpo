import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { getGlobalStats, getVotoLimpoStats, ncStatsToStats } from "@/lib/nc-api";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://votolimpo.com.br"),
  title: {
    default: "Voto Limpo — Transparência Política",
    template: "%s | Voto Limpo",
  },
  description:
    "Plataforma de transparência política brasileira. Acompanhe o histórico, vínculos e índice de transparência dos políticos do Brasil.",
  keywords: [
    "transparência",
    "política",
    "Brasil",
    "corrupção",
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
    title: "Voto Limpo — Transparência Política",
    description:
      "Acompanhe o histórico e vínculos dos políticos brasileiros com transparência e dados verificados.",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Voto Limpo — Transparência Política Brasileira",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@votolimpo",
    creator: "@votolimpo",
    title: "Voto Limpo — Transparência Política",
    description: "Acompanhe o histórico e vínculos dos políticos brasileiros.",
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
    const [ncStats, vlStats] = await Promise.all([
      getGlobalStats(),
      getVotoLimpoStats(),
    ]);
    stats = ncStatsToStats(ncStats, vlStats);
  } catch {
    // Fallback stats if NC API is unavailable
    stats = {
      totalPoliticians: 0,
      totalArticles: 0,
      totalEntities: 0,
      totalSources: 0,
      avgScore: null,
      criticalCount: 0,
    };
  }

  return (
    <html lang="pt-BR" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen bg-[#0A0A0A] text-[#FAFAFA] flex flex-col antialiased font-sans">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer stats={stats} />
      </body>
    </html>
  );
}
