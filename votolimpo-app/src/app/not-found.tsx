import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      {/* Icon: magnifying glass with X */}
      <svg
        className="h-16 w-16 text-emerald-400 opacity-80"
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
          d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 9l4 4m0-4l-4 4"
        />
      </svg>

      <h1 className="text-3xl font-bold text-[#FAFAFA] mt-6">
        Pagina nao encontrada
      </h1>

      <p className="text-[#6B7280] mt-3 max-w-md">
        A pagina que voce procura nao existe ou foi movida. Verifique o endereco
        ou navegue para a pagina inicial.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <Link
          href="/"
          className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-600 transition-colors"
        >
          Voltar ao inicio
        </Link>
        <Link
          href="/busca"
          className="rounded-xl border border-[#2E2E2E] bg-[#0A0A0A] px-6 py-3 text-sm font-semibold text-[#FAFAFA] hover:border-emerald-500/50 hover:bg-[#1A1A1A] transition-colors"
        >
          Buscar politico
        </Link>
      </div>
    </div>
  );
}
