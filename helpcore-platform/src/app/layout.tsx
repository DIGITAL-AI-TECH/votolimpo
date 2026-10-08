import type { Metadata } from "next";
import { Nunito_Sans } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

const nunitoSans = Nunito_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-nunito-sans",
});

export const metadata: Metadata = {
  title: "Help Core Platform",
  description: "Plataforma de gestao e qualidade da base de conhecimento Help Bradesco",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className={nunitoSans.variable}>
      <body className="min-h-screen bg-black text-[#D4D8DD] font-[family-name:var(--font-nunito-sans)] antialiased">
        <Navbar />
        <main className="mx-auto max-w-7xl">{children}</main>
      </body>
    </html>
  );
}
