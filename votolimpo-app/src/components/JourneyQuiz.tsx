"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARGOS = [
  { value: "PRESIDENTE", label: "Presidente da Republica", icon: "crown" },
  { value: "GOVERNADOR", label: "Governador de Estado", icon: "building" },
  { value: "SENADOR", label: "Senador", icon: "scroll" },
  { value: "DEPUTADO FEDERAL", label: "Deputado Federal", icon: "flag" },
  { value: "DEPUTADO ESTADUAL", label: "Deputado Estadual", icon: "map-pin" },
] as const;

const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO",
  "MA","MG","MS","MT","PA","PB","PE","PI","PR",
  "RJ","RN","RO","RR","RS","SC","SE","SP","TO",
] as const;

const UF_NAMES: Record<string, string> = {
  AC:"Acre",AL:"Alagoas",AM:"Amazonas",AP:"Amapa",BA:"Bahia",CE:"Ceara",
  DF:"Distrito Federal",ES:"Espirito Santo",GO:"Goias",MA:"Maranhao",
  MG:"Minas Gerais",MS:"Mato Grosso do Sul",MT:"Mato Grosso",PA:"Para",
  PB:"Paraiba",PE:"Pernambuco",PI:"Piaui",PR:"Parana",RJ:"Rio de Janeiro",
  RN:"Rio Grande do Norte",RO:"Rondonia",RR:"Roraima",RS:"Rio Grande do Sul",
  SC:"Santa Catarina",SE:"Sergipe",SP:"Sao Paulo",TO:"Tocantins",
};

// ---------------------------------------------------------------------------
// Icons (inline SVG to avoid deps)
// ---------------------------------------------------------------------------

function CargoIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "crown":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2 20h20M5 20V9l4 3 3-7 3 7 4-3v11" />
        </svg>
      );
    case "building":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 21h18M3 7v14m18-14v14M6 11h.01M6 15h.01M6 7h.01M10 11h.01M10 15h.01M10 7h.01M14 11h.01M14 15h.01M14 7h.01M18 11h.01M18 15h.01M18 7h.01" />
        </svg>
      );
    case "scroll":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case "flag":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z" />
        </svg>
      );
    case "map-pin":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
        </svg>
      );
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface JourneyQuizProps {
  /** If true, renders inline (not modal) — for the CTA card on home */
  inline?: boolean;
  onComplete?: (cargo: string, uf?: string) => void;
  onSkip?: () => void;
}

export default function JourneyQuiz({ inline, onComplete, onSkip }: JourneyQuizProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<1 | 2>(1);
  const [selectedCargo, setSelectedCargo] = useState<string | null>(null);
  const [selectedUf, setSelectedUf] = useState<string | null>(null);
  const [ufSearch, setUfSearch] = useState("");

  // If cargo is already in URL, jump to step 2
  useEffect(() => {
    const urlCargo = searchParams.get("cargo");
    if (urlCargo) {
      setSelectedCargo(urlCargo.toUpperCase());
      if (urlCargo.toUpperCase() !== "PRESIDENTE") {
        setStep(2);
      }
    }
  }, [searchParams]);

  const handleCargoSelect = useCallback(
    (cargoValue: string) => {
      setSelectedCargo(cargoValue);
      if (cargoValue === "PRESIDENTE") {
        // No UF needed for president
        navigateToDashboard(cargoValue, undefined);
      } else {
        setTimeout(() => setStep(2), 200);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const handleUfSelect = useCallback(
    (uf: string) => {
      setSelectedUf(uf);
      setTimeout(() => {
        if (selectedCargo) {
          navigateToDashboard(selectedCargo, uf);
        }
      }, 200);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedCargo],
  );

  function navigateToDashboard(cargo: string, uf?: string) {
    // Save to localStorage
    try {
      localStorage.setItem(
        "vl_context",
        JSON.stringify({
          cargo,
          uf: uf || null,
          set_at: new Date().toISOString(),
        }),
      );
    } catch {
      // SSR or private browsing
    }

    if (onComplete) {
      onComplete(cargo, uf || undefined);
      return;
    }

    const params = new URLSearchParams();
    params.set("cargo", cargo.toLowerCase());
    if (uf) params.set("uf", uf);
    router.push(`/?${params.toString()}`);
  }

  const filteredUfs = ufSearch
    ? UFS.filter(
        (uf) =>
          uf.toLowerCase().includes(ufSearch.toLowerCase()) ||
          UF_NAMES[uf]?.toLowerCase().includes(ufSearch.toLowerCase()),
      )
    : UFS;

  const containerClass = inline
    ? ""
    : "fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4";

  const cardClass = inline
    ? "rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6"
    : "relative w-full max-w-md rounded-2xl border border-[#2E2E2E] bg-[#0F0F0F] p-6 shadow-2xl max-h-[90vh] overflow-y-auto";

  return (
    <div className={containerClass} onClick={!inline ? onSkip : undefined}>
      <div className={cardClass} onClick={(e) => e.stopPropagation()}>
        {/* Progress */}
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {step === 2 && (
              <button
                onClick={() => { setStep(1); setSelectedUf(null); }}
                className="mr-2 rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#1A1A1A] hover:text-[#FAFAFA]"
                aria-label="Voltar"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            )}
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${step >= 1 ? "bg-emerald-400" : "bg-[#2E2E2E]"}`} />
              <span className={`h-2 w-2 rounded-full ${step >= 2 ? "bg-emerald-400" : "bg-[#2E2E2E]"}`} />
            </div>
            <span className="text-xs text-[#6B7280]">
              Passo {step} de 2
            </span>
          </div>
          {!inline && onSkip && (
            <button
              onClick={onSkip}
              className="rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#1A1A1A] hover:text-[#FAFAFA]"
              aria-label="Fechar"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Step 1: Cargo selection */}
        {step === 1 && (
          <div>
            <h2 className="text-lg font-bold text-[#FAFAFA]">
              Para qual cargo voce quer ver os candidatos?
            </h2>
            <p className="mt-1 text-sm text-[#6B7280]">
              Selecione para ver um painel personalizado
            </p>

            <div className="mt-5 flex flex-col gap-2.5">
              {CARGOS.map((cargo) => (
                <button
                  key={cargo.value}
                  onClick={() => handleCargoSelect(cargo.value)}
                  className={`flex items-center gap-3 rounded-xl border px-4 py-3.5 text-left transition-all duration-150 ${
                    selectedCargo === cargo.value
                      ? "border-emerald-400 bg-emerald-500/10 text-emerald-400"
                      : "border-[#2E2E2E] bg-[#141414] text-[#FAFAFA] hover:border-[#3E3E3E] hover:bg-[#1A1A1A]"
                  }`}
                >
                  <span className={`flex-shrink-0 ${selectedCargo === cargo.value ? "text-emerald-400" : "text-[#6B7280]"}`}>
                    <CargoIcon icon={cargo.icon} />
                  </span>
                  <span className="text-sm font-medium">{cargo.label}</span>
                  {selectedCargo === cargo.value && (
                    <svg className="ml-auto h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}
            </div>

            {!inline && (
              <button
                onClick={onSkip}
                className="mt-5 w-full text-center text-sm text-[#6B7280] transition-colors hover:text-emerald-400"
              >
                Explorar todos os candidatos &rarr;
              </button>
            )}
          </div>
        )}

        {/* Step 2: UF selection */}
        {step === 2 && (
          <div>
            <h2 className="text-lg font-bold text-[#FAFAFA]">
              Em qual estado voce vai votar?
            </h2>
            <p className="mt-1 text-sm text-[#6B7280]">
              Selecione seu estado para ver os candidatos da sua regiao
            </p>

            {/* Search */}
            <div className="relative mt-4">
              <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B7280]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={ufSearch}
                onChange={(e) => setUfSearch(e.target.value)}
                placeholder="Buscar estado..."
                className="w-full rounded-xl border border-[#2E2E2E] bg-[#141414] py-2.5 pl-10 pr-4 text-sm text-[#FAFAFA] placeholder-[#6B7280] outline-none transition-colors focus:border-emerald-500/50"
              />
            </div>

            {/* UF Grid */}
            <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-7">
              {filteredUfs.map((uf) => (
                <button
                  key={uf}
                  onClick={() => handleUfSelect(uf)}
                  title={UF_NAMES[uf]}
                  className={`rounded-lg border py-2.5 text-center text-xs font-bold transition-all duration-150 ${
                    selectedUf === uf
                      ? "border-emerald-400 bg-emerald-500/10 text-emerald-400"
                      : "border-[#2E2E2E] bg-[#141414] text-[#FAFAFA] hover:border-[#3E3E3E] hover:bg-[#1A1A1A]"
                  }`}
                >
                  {uf}
                </button>
              ))}
            </div>

            {filteredUfs.length === 0 && (
              <p className="mt-4 text-center text-sm text-[#6B7280]">
                Nenhum estado encontrado
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
