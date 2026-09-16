import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Voto Limpo — Transparencia Politica",
    short_name: "Voto Limpo",
    description:
      "Plataforma de transparencia politica brasileira. Acompanhe o historico, vinculos e indice de transparencia dos politicos do Brasil.",
    start_url: "/",
    display: "standalone",
    background_color: "#0A0A0A",
    theme_color: "#10B981",
    orientation: "portrait-primary",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icons/icon-192x192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512x512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/maskable-512x512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    categories: ["news", "politics", "government"],
    lang: "pt-BR",
    dir: "ltr",
  };
}
