"use client";

import { useEffect } from "react";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    console.error("[VotoLimpo] Global error:", error);
  }, [error]);

  return (
    <html lang="pt-BR" className="dark">
      <body className="min-h-screen bg-[#0A0A0A] text-[#FAFAFA] flex flex-col items-center justify-center px-4 antialiased">
        {/* Logo */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- global-error cannot use next/link (outside root layout) */}
        <a href="/" className="text-lg font-bold tracking-tight mb-12">
          Voto<span className="text-emerald-400">Limpo</span>
        </a>

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
          Erro critico
        </h1>

        <p className="text-[#6B7280] mt-3 max-w-md text-center">
          A aplicacao encontrou um erro grave. Clique abaixo para recarregar.
        </p>

        <button
          onClick={() => reset()}
          className="mt-8 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-600 transition-colors"
        >
          Recarregar pagina
        </button>

        {error.digest && (
          <p className="mt-6 text-xs text-[#6B7280]">Codigo: {error.digest}</p>
        )}
      </body>
    </html>
  );
}
