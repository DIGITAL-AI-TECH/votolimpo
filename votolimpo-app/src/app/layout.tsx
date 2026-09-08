import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { getStats } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: {
    default: "Voto Limpo — Transparência Política",
    template: "%s | Voto Limpo",
  },
  description:
    "Plataforma de transparência política brasileira. Acompanhe o histórico, vínculos e índice de transparência dos políticos do Brasil.",
  keywords: ["transparência", "política", "Brasil", "corrupção", "eleições", "democracia"],
  authors: [{ name: "Voto Limpo" }],
  openGraph: {
    type: "website",
    locale: "pt_BR",
    url: "https://votolimpo.com.br",
    siteName: "Voto Limpo",
    title: "Voto Limpo — Transparência Política",
    description: "Acompanhe o histórico e vínculos dos políticos brasileiros com transparência e dados verificados.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Voto Limpo — Transparência Política",
    description: "Acompanhe o histórico e vínculos dos políticos brasileiros.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const stats = getStats();

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
