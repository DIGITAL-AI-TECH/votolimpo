"use client";

import { useEffect } from "react";
import Link from "next/link";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error("[VotoLimpo] Route error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      {/* Icon: triangle with exclamation */}
      <svg
        className="h-16 w-16 text-red-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
        />
      </svg>

      <h1 className="text-3xl font-bold text-[#FAFAFA] mt-6">
        Algo deu errado
      </h1>

      <p className="text-[#6B7280] mt-3 max-w-md">
        Ocorreu um erro inesperado. Tente novamente ou volte para a pagina
        inicial.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <button
          onClick={() => reset()}
          className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-600 transition-colors"
        >
          Tentar novamente
        </button>
        <Link
          href="/"
          className="rounded-xl border border-[#2E2E2E] bg-[#0A0A0A] px-6 py-3 text-sm font-semibold text-[#FAFAFA] hover:border-emerald-500/50 hover:bg-[#1A1A1A] transition-colors"
        >
          Voltar ao inicio
        </Link>
      </div>

      {error.digest && (
        <p className="mt-6 text-xs text-[#6B7280]">Codigo: {error.digest}</p>
      )}
    </div>
  );
}
