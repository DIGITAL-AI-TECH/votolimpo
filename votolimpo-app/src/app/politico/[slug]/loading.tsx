function ArticleCardSkeleton() {
  return (
    <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 animate-pulse">
      {/* Header row: severity + source */}
      <div className="flex items-center justify-between">
        <div className="h-5 w-14 bg-[#1A1A1A] rounded" />
        <div className="h-3 w-20 bg-[#1A1A1A] rounded" />
      </div>
      {/* Title */}
      <div className="h-4 w-full bg-[#1A1A1A] rounded mt-2" />
      <div className="h-4 w-3/4 bg-[#1A1A1A] rounded mt-1" />
      {/* Summary */}
      <div className="h-3 w-full bg-[#1A1A1A] rounded mt-2" />
      <div className="h-3 w-2/3 bg-[#1A1A1A] rounded mt-1" />
      {/* Tags + score row */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex gap-2">
          <div className="h-5 w-12 bg-[#1A1A1A] rounded" />
          <div className="h-5 w-16 bg-[#1A1A1A] rounded" />
          <div className="h-5 w-10 bg-[#1A1A1A] rounded" />
        </div>
        <div className="h-3 w-16 bg-[#1A1A1A] rounded" />
      </div>
    </div>
  );
}

export default function PoliticoLoading() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8 animate-pulse">
      {/* Profile Header Skeleton */}
      <div className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-6 mb-6">
        <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
          {/* Profile photo */}
          <div className="w-24 h-24 bg-[#1A1A1A] rounded-full flex-shrink-0" />

          {/* Info */}
          <div className="flex-1 text-center sm:text-left">
            <div className="h-8 w-48 bg-[#1A1A1A] rounded mx-auto sm:mx-0" />
            <div className="h-4 w-32 bg-[#1A1A1A] rounded mt-2 mx-auto sm:mx-0" />

            {/* Badges + score */}
            <div className="mt-4 flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <div className="h-6 w-16 bg-[#1A1A1A] rounded" />
              <div className="h-6 w-10 bg-[#1A1A1A] rounded" />
              <div className="h-8 w-20 bg-[#1A1A1A] rounded" />
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards Grid */}
      <div className="grid grid-cols-2 gap-4 mb-8 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-[#2E2E2E] bg-[#141414] p-4 h-24 flex flex-col justify-between"
          >
            <div className="h-3 w-20 bg-[#1A1A1A] rounded" />
            <div className="h-8 w-16 bg-[#1A1A1A] rounded" />
          </div>
        ))}
      </div>

      {/* Timeline / Articles Skeleton */}
      <div>
        <div className="h-6 w-40 bg-[#1A1A1A] rounded mb-4" />
        <div className="flex flex-col gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <ArticleCardSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
