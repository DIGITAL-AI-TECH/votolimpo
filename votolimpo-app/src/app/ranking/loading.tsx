export default function RankingLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 animate-pulse">
      {/* Page Header Skeleton */}
      <div className="mb-8">
        <div className="h-8 w-48 bg-[#1A1A1A] rounded" />
        <div className="mt-1 h-4 w-72 bg-[#1A1A1A] rounded" />
      </div>

      {/* Filters Skeleton */}
      <div className="mb-6 flex flex-wrap gap-3">
        <div className="h-10 w-40 bg-[#1A1A1A] rounded-lg" />
        <div className="h-10 w-32 bg-[#1A1A1A] rounded-lg" />
      </div>

      {/* Table Skeleton */}
      <div className="rounded-xl border border-[#2E2E2E] overflow-hidden">
        {/* Table header */}
        <div className="bg-[#141414] px-4 h-10 flex items-center gap-4 border-b border-[#2E2E2E]">
          <div className="h-3 w-8 bg-[#2E2E2E] rounded" />
          <div className="h-3 w-32 bg-[#2E2E2E] rounded" />
          <div className="h-3 w-20 bg-[#2E2E2E] rounded ml-auto" />
          <div className="h-3 w-16 bg-[#2E2E2E] rounded" />
          <div className="h-3 w-16 bg-[#2E2E2E] rounded" />
        </div>

        {/* Table rows */}
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className={`px-4 h-14 flex items-center gap-4 border-b border-[#2E2E2E] ${
              i % 2 === 0 ? "bg-[#0A0A0A]" : "bg-[#141414]"
            }`}
          >
            <div className="h-3 w-6 bg-[#1A1A1A] rounded flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="h-4 w-36 bg-[#1A1A1A] rounded" />
              <div className="h-3 w-24 bg-[#1A1A1A] rounded mt-1" />
            </div>
            <div className="h-5 w-14 bg-[#1A1A1A] rounded flex-shrink-0" />
            <div className="h-5 w-10 bg-[#1A1A1A] rounded flex-shrink-0" />
            <div className="h-7 w-14 bg-[#1A1A1A] rounded flex-shrink-0" />
          </div>
        ))}
      </div>

      {/* Pagination Skeleton */}
      <div className="mt-6 flex items-center justify-between">
        <div className="h-9 w-24 bg-[#1A1A1A] rounded-lg" />
        <div className="h-4 w-32 bg-[#1A1A1A] rounded" />
        <div className="h-9 w-24 bg-[#1A1A1A] rounded-lg" />
      </div>
    </div>
  );
}
