"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type { Politician, SortField, SortOrder } from "@/types";
import RankingTable from "@/components/RankingTable";

const PAGE_SIZE = 20;

const CARGO_OPTIONS = [
  { value: "", label: "Todos os cargos" },
  { value: "presidente", label: "Presidente" },
  { value: "governador", label: "Governador" },
  { value: "senador", label: "Senador" },
  { value: "deputado federal", label: "Deputado Federal" },
  { value: "deputado estadual", label: "Deputado Estadual" },
];

function RankingPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortField>("name");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [selectedParty, setSelectedParty] = useState("");
  const [selectedUF, setSelectedUF] = useState("");
  const [selectedCargo, setSelectedCargo] = useState("");
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [total, setTotal] = useState(0);
  const [parties, setParties] = useState<string[]>([]);
  const [ufs, setUfs] = useState<string[]>([]);
  const [, setCargos] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Initialize cargo from URL param on mount
  useEffect(() => {
    const urlCargo = searchParams.get("cargo");
    if (urlCargo) {
      setSelectedCargo(urlCargo.toLowerCase());
    }
    const urlUf = searchParams.get("uf");
    if (urlUf) {
      setSelectedUF(urlUf.toUpperCase());
    }
  }, [searchParams]);

  // Fetch filter options once from dedicated endpoint
  useEffect(() => {
    fetch("/api/filters")
      .then((res) => res.json())
      .then((data) => {
        setParties(data.parties || []);
        setUfs(data.states || []);
        setCargos(data.cargos || []);
      })
      .catch((err) => console.error("Failed to fetch filters:", err));
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        pageSize: String(PAGE_SIZE),
        sortBy,
        sortOrder,
      });
      if (selectedParty) params.set("party", selectedParty);
      if (selectedUF) params.set("uf", selectedUF);
      if (selectedCargo) params.set("cargo", selectedCargo);

      const res = await fetch(`/api/ranking?${params}`);
      if (!res.ok) throw new Error("Failed to fetch");

      const data = await res.json();
      setPoliticians(data.data || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch ranking:", error);
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, sortOrder, selectedParty, selectedUF, selectedCargo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Sync selected cargo to URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (selectedCargo) {
      params.set("cargo", selectedCargo);
    } else {
      params.delete("cargo");
    }
    if (selectedUF) {
      params.set("uf", selectedUF);
    } else {
      params.delete("uf");
    }
    const qs = params.toString();
    const newUrl = qs ? `?${qs}` : window.location.pathname;
    router.replace(newUrl, { scroll: false });
  }, [selectedCargo, selectedUF, router]);

  const handleSortChange = (field: SortField, order: SortOrder) => {
    setSortBy(field);
    setSortOrder(order);
    setPage(1);
  };

  const handleFilterChange = (type: "party" | "uf" | "cargo", value: string) => {
    if (type === "party") setSelectedParty(value);
    if (type === "uf") setSelectedUF(value);
    if (type === "cargo") setSelectedCargo(value);
    setPage(1);
  };

  const clearFilters = () => {
    setSelectedParty("");
    setSelectedUF("");
    setSelectedCargo("");
    setPage(1);
  };

  const hasFilters = selectedParty || selectedUF || selectedCargo;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#FAFAFA]">Ranking de Candidatos</h1>
        <p className="mt-2 text-[#6B7280]">
          Todos os candidatos monitorados. Clique nas colunas para reordenar.
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
        <select
          value={selectedCargo}
          onChange={(e) => handleFilterChange("cargo", e.target.value)}
          aria-label="Filtrar por cargo"
          className="rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-500/50"
        >
          {CARGO_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        <select
          value={selectedParty}
          onChange={(e) => handleFilterChange("party", e.target.value)}
          aria-label="Filtrar por partido"
          className="rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-500/50"
        >
          <option value="">Todos os partidos</option>
          {parties.map((party) => (
            <option key={party} value={party}>{party}</option>
          ))}
        </select>

        <select
          value={selectedUF}
          onChange={(e) => handleFilterChange("uf", e.target.value)}
          aria-label="Filtrar por estado"
          className="rounded-lg border border-[#2E2E2E] bg-[#0A0A0A] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-500/50"
        >
          <option value="">Todos os estados</option>
          {ufs.map((uf) => (
            <option key={uf} value={uf}>{uf}</option>
          ))}
        </select>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs text-[#6B7280] hover:text-[#FAFAFA] transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Limpar filtros
          </button>
        )}

        <div className="ml-auto flex items-center gap-2 text-xs text-[#6B7280]">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
          </svg>
          Clique nos cabeçalhos para ordenar
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        </div>
      ) : (
        <RankingTable
          politicians={politicians}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          onSortChange={handleSortChange}
          sortField={sortBy}
          sortOrder={sortOrder}
        />
      )}

      {/* Legend */}
      <div className="mt-8 rounded-xl border border-[#2E2E2E] bg-[#141414] p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
          Legenda — Índice de Transparência
        </h3>
        <div className="flex flex-wrap gap-4">
          {[
            { range: "80-100", label: "Excelente", color: "text-emerald-400", dot: "bg-emerald-400" },
            { range: "60-79", label: "Bom", color: "text-blue-400", dot: "bg-blue-400" },
            { range: "40-59", label: "Regular", color: "text-yellow-400", dot: "bg-yellow-400" },
            { range: "20-39", label: "Preocupante", color: "text-orange-400", dot: "bg-orange-400" },
            { range: "0-19", label: "Crítico", color: "text-red-400", dot: "bg-red-400" },
          ].map((item) => (
            <div key={item.range} className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${item.dot}`} />
              <span className={`font-mono text-xs font-bold ${item.color}`}>{item.range}</span>
              <span className="text-xs text-[#6B7280]">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RankingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        </div>
      }
    >
      <RankingPageInner />
    </Suspense>
  );
}
