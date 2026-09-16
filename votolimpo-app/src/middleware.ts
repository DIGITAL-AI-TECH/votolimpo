import { NextRequest, NextResponse } from "next/server";

// Rate limits por rota (req/min)
const RATE_LIMITS: Record<string, number> = {
  "/api/search": 20,
  "/api/articles": 30,
  "/api/politicians": 30,
  "/api/ranking": 20,
  "/api/stats": 60,
  "/api/graph": 20,
};
const DEFAULT_LIMIT = 30;
const WINDOW_MS = 60_000;

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

// Map<"ip:routeKey", entry>
const store = new Map<string, RateLimitEntry>();

// Cleanup de entries expiradas a cada 60s para evitar memory leak
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of store) {
    if (val.resetAt <= now) store.delete(key);
  }
}, 60_000);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Aplicar rate limiting apenas em rotas /api/*
  if (!pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // Extrair IP do cliente (via proxy Traefik/Next.js)
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown";

  // Selecionar limite da rota mais específica que corresponde ao pathname
  const routeKey =
    Object.keys(RATE_LIMITS)
      .filter((r) => pathname.startsWith(r))
      .sort((a, b) => b.length - a.length)[0] ?? null;

  const limit = routeKey !== null ? RATE_LIMITS[routeKey] : DEFAULT_LIMIT;
  const storeKey = `${ip}:${routeKey ?? "/api"}`;
  const now = Date.now();

  let entry = store.get(storeKey);

  // Criar ou resetar janela expirada
  if (!entry || entry.resetAt <= now) {
    entry = { count: 0, resetAt: now + WINDOW_MS };
    store.set(storeKey, entry);
  }

  entry.count++;
  const remaining = Math.max(0, limit - entry.count);
  const retryAfter = Math.ceil((entry.resetAt - now) / 1000);

  // Excedeu o limite — retornar 429
  if (entry.count > limit) {
    return NextResponse.json(
      { error: "Too many requests. Please try again later." },
      {
        status: 429,
        headers: {
          "Retry-After": String(retryAfter),
          "X-RateLimit-Limit": String(limit),
          "X-RateLimit-Remaining": "0",
        },
      }
    );
  }

  // Dentro do limite — adicionar headers informativos
  const response = NextResponse.next();
  response.headers.set("X-RateLimit-Limit", String(limit));
  response.headers.set("X-RateLimit-Remaining", String(remaining));
  return response;
}

export const config = {
  matcher: "/api/:path*",
};
