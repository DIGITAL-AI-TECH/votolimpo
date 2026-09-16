import type { MetadataRoute } from "next";
import { listEntities } from "@/lib/nc-api";

export const revalidate = 3600; // 1 hora

const BASE_URL = "https://votolimpo.com.br";

const STATIC_PAGES: MetadataRoute.Sitemap = [
  {
    url: BASE_URL,
    lastModified: new Date(),
    changeFrequency: "daily",
    priority: 1.0,
  },
  {
    url: `${BASE_URL}/ranking`,
    lastModified: new Date(),
    changeFrequency: "daily",
    priority: 0.9,
  },
  {
    url: `${BASE_URL}/busca`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.7,
  },
  {
    url: `${BASE_URL}/grafo`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.7,
  },
  {
    url: `${BASE_URL}/como-funciona`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.5,
  },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let politicianUrls: MetadataRoute.Sitemap = [];

  try {
    const entities = await listEntities({
      type: "candidate",
      active: true,
      limit: 50000,
    });

    politicianUrls = entities.map((entity) => ({
      url: `${BASE_URL}/politico/${entity.slug}`,
      lastModified: new Date(entity.updated_at),
      changeFrequency: "daily" as const,
      priority: 0.8,
    }));
  } catch (err) {
    console.error("[sitemap] Falha ao buscar entidades — usando apenas paginas estaticas:", err);
  }

  return [...STATIC_PAGES, ...politicianUrls];
}
