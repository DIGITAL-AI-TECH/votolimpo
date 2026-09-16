import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/_next/"],
      },
    ],
    sitemap: "https://votolimpo.digital-ai.tech/sitemap.xml",
    host: "https://votolimpo.digital-ai.tech",
  };
}
