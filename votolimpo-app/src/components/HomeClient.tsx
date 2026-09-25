"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import JourneyQuiz from "./JourneyQuiz";
import ContextDashboard from "./ContextDashboard";

// ---------------------------------------------------------------------------
// Inner component that reads searchParams (must be wrapped in Suspense)
// ---------------------------------------------------------------------------

function HomeClientInner({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [showQuiz, setShowQuiz] = useState(false);
  const [contextCargo, setContextCargo] = useState<string | null>(null);
  const [contextUf, setContextUf] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // On mount: check URL params first, then localStorage
  useEffect(() => {
    const urlCargo = searchParams.get("cargo");
    const urlUf = searchParams.get("uf");

    if (urlCargo) {
      setContextCargo(urlCargo.toUpperCase());
      setContextUf(urlUf?.toUpperCase() || null);
      setReady(true);
      return;
    }

    // Check localStorage for saved context
    try {
      const saved = localStorage.getItem("vl_context");
      if (saved) {
        const ctx = JSON.parse(saved);
        if (ctx.cargo) {
          // Check expiry (30 days)
          const setAt = new Date(ctx.set_at || 0).getTime();
          const now = Date.now();
          if (now - setAt < 30 * 24 * 60 * 60 * 1000) {
            setContextCargo(ctx.cargo.toUpperCase());
            setContextUf(ctx.uf?.toUpperCase() || null);
            // Update URL silently
            const params = new URLSearchParams();
            params.set("cargo", ctx.cargo.toLowerCase());
            if (ctx.uf) params.set("uf", ctx.uf);
            router.replace(`/?${params.toString()}`, { scroll: false });
            setReady(true);
            return;
          }
        }
      }
    } catch {
      // SSR or parse error
    }

    // No context — show default home (with quiz CTA)
    setReady(true);
  }, [searchParams, router]);

  const handleQuizComplete = useCallback(
    (cargo: string, uf?: string) => {
      setContextCargo(cargo.toUpperCase());
      setContextUf(uf?.toUpperCase() || null);
      setShowQuiz(false);

      const params = new URLSearchParams();
      params.set("cargo", cargo.toLowerCase());
      if (uf) params.set("uf", uf);
      router.push(`/?${params.toString()}`, { scroll: false });
    },
    [router],
  );

  const handleChangeContext = useCallback(() => {
    setShowQuiz(true);
  }, []);

  const handleSkipQuiz = useCallback(() => {
    setShowQuiz(false);
  }, []);

  const handleStartQuiz = useCallback(() => {
    setShowQuiz(true);
  }, []);

  // Not ready yet — show nothing (prevents flash)
  if (!ready) return null;

  // Quiz modal open
  if (showQuiz) {
    return (
      <JourneyQuiz
        onComplete={handleQuizComplete}
        onSkip={handleSkipQuiz}
      />
    );
  }

  // Has context → show dashboard
  if (contextCargo) {
    return (
      <ContextDashboard
        cargo={contextCargo}
        uf={contextUf || undefined}
        onChangeContext={handleChangeContext}
      />
    );
  }

  // No context → show default home with quiz CTA injected
  return (
    <div>
      {/* Quiz CTA Card — injected before the server-rendered children */}
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 -mt-4 mb-8">
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-base font-bold text-[#FAFAFA]">
                Descubra seus candidatos
              </h3>
              <p className="mt-1 text-sm text-[#6B7280]">
                Selecione seu estado e cargo para ver um painel personalizado
                com os candidatos da sua regiao.
              </p>
            </div>
            <button
              onClick={handleStartQuiz}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-600 flex-shrink-0"
            >
              Comecar agora
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported wrapper with Suspense boundary
// ---------------------------------------------------------------------------

export default function HomeClient({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div>{children}</div>}>
      <HomeClientInner>{children}</HomeClientInner>
    </Suspense>
  );
}
