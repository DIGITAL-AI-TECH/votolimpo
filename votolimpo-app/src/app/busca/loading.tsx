function PoliticianCardSkeleton() {
  return (
    <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 animate-pulse">
      <div className="flex items-start gap-3">
        {/* Rank */}
        <div className="w-8 h-8 bg-[#1A1A1A] rounded flex-shrink-0" />
        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="h-4 w-32 bg-[#1A1A1A] rounded" />
          <div className="h-3 w-24 bg-[#1A1A1A] rounded mt-1" />
          <div className="flex gap-2 mt-3">
            <div className="h-5 w-12 bg-[#1A1A1A] rounded" />
            <div className="h-5 w-8 bg-[#1A1A1A] rounded" />
          </div>
          <div className="flex gap-4 mt-3">
            <div className="h-3 w-16 bg-[#1A1A1A] rounded" />
            <div className="h-3 w-16 bg-[#1A1A1A] rounded" />
          </div>
        </div>
        {/* Score */}
        <div className="h-6 w-10 bg-[#1A1A1A] rounded flex-shrink-0" />
      </div>
    </div>
  );
}

export default function BuscaLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 animate-pulse">
      {/* Search Header */}
      <div className="mb-6">
        <div className="h-8 w-32 bg-[#1A1A1A] rounded" />
        <div className="mt-4 h-12 w-full bg-[#1A1A1A] rounded-xl" />
      </div>

      {/* Results count */}
      <div className="mb-6 h-4 w-40 bg-[#1A1A1A] rounded" />

      {/* Results Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <PoliticianCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
