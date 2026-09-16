import { NextResponse } from "next/server";

export async function GET() {
  try {
    // Verificacao basica: o NC API esta acessivel?
    const NC_API_URL =
      process.env.NC_API_URL || "https://api.news-collector.digital-ai.tech";
    const NC_API_TOKEN = process.env.NC_API_TOKEN || "";

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5_000);

    const res = await fetch(`${NC_API_URL}/stats/`, {
      headers: { Authorization: `Bearer ${NC_API_TOKEN}` },
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return NextResponse.json(
        { status: "degraded", nc_api: "unreachable", code: res.status },
        { status: 503 }
      );
    }

    return NextResponse.json({ status: "healthy", nc_api: "ok" });
  } catch (error) {
    return NextResponse.json(
      { status: "unhealthy", nc_api: "error", error: String(error) },
      { status: 503 }
    );
  }
}

// Health check DEVE ser force-dynamic — nunca cachear
export const dynamic = "force-dynamic";
