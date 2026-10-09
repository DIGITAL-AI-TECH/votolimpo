import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

const ADMIN_KEY = process.env.HELPCORE_AUTH_SECRET;

function checkAuth(request: NextRequest): boolean {
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !ADMIN_KEY) return false;
  const token = authHeader.replace("Bearer ", "");
  if (token.length !== ADMIN_KEY.length) return false;
  let mismatch = 0;
  for (let i = 0; i < token.length; i++) {
    mismatch |= token.charCodeAt(i) ^ ADMIN_KEY.charCodeAt(i);
  }
  return mismatch === 0;
}

interface ArticleUpdate {
  source_url: string;
  content?: string | null;
  html_content?: string | null;
  content_hash?: string | null;
}

export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await request.json();
    const articles: ArticleUpdate[] = body.articles;

    if (!Array.isArray(articles) || articles.length === 0) {
      return NextResponse.json({ error: "articles array required" }, { status: 400 });
    }

    if (articles.length > 200) {
      return NextResponse.json({ error: "max 200 articles per batch" }, { status: 400 });
    }

    let updated = 0;
    let notFound = 0;

    // Process in individual updates using raw SQL for performance
    for (const article of articles) {
      if (!article.source_url) continue;

      const result = await prisma.$executeRawUnsafe(
        `UPDATE help_core.articles
         SET content = COALESCE($1, content),
             html_content = COALESCE($2, html_content),
             content_hash = COALESCE($3, content_hash)
         WHERE source_url = $4`,
        article.content ?? null,
        article.html_content ?? null,
        article.content_hash ?? null,
        article.source_url
      );

      if (result > 0) {
        updated++;
      } else {
        notFound++;
      }
    }

    return NextResponse.json({ updated, not_found: notFound, total: articles.length });
  } catch (error) {
    console.error("Bulk content error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
