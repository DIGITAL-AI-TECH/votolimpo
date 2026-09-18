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
      // Return 200 with degraded status — the app itself is healthy,
      // only the NC API dependency is unreachable. Returning 503 here
      // causes Docker Swarm healthcheck to kill the container.
      return NextResponse.json(
        { status: "degraded", nc_api: "unreachable", code: res.status },
        { status: 200 }
      );
    }

    return NextResponse.json({ status: "healthy", nc_api: "ok" });
  } catch {
    // App process is alive — return 200 even if NC API is down.
    // Swarm healthcheck must not kill the container for a dependency failure.
    return NextResponse.json(
      { status: "degraded", nc_api: "error" },
      { status: 200 }
    );
  }
}

// Health check DEVE ser force-dynamic — nunca cachear
export const dynamic = "force-dynamic";
