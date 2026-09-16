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

export default function HomeLoading() {
  return (
    <div className="min-h-screen">
      {/* Hero Section Skeleton */}
      <section className="border-b border-[#1A1A1A] py-20 md:py-32">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8 animate-pulse">
          {/* Badge */}
          <div className="mx-auto h-6 w-48 bg-[#1A1A1A] rounded-full" />
          {/* Title */}
          <div className="mx-auto mt-6 h-12 w-96 bg-[#1A1A1A] rounded max-w-full" />
          {/* Subtitle */}
          <div className="mx-auto mt-2 h-4 w-80 bg-[#1A1A1A] rounded max-w-full" />
          {/* Search bar */}
          <div className="mx-auto mt-10 h-12 w-full max-w-xl bg-[#1A1A1A] rounded-xl" />
          {/* Stats row */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-6 md:gap-10">
            {[1, 2, 3].map((i) => (
              <div key={i} className="text-center">
                <div className="mx-auto h-10 w-24 bg-[#1A1A1A] rounded" />
                <div className="mx-auto mt-1 h-3 w-20 bg-[#1A1A1A] rounded" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Candidates Section Skeleton */}
      <section className="py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between animate-pulse">
            <div>
              <div className="h-8 w-64 bg-[#1A1A1A] rounded" />
              <div className="mt-1 h-4 w-40 bg-[#1A1A1A] rounded" />
            </div>
            <div className="h-9 w-36 bg-[#1A1A1A] rounded-lg" />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <PoliticianCardSkeleton key={i} />
            ))}
          </div>
        </div>
      </section>

      {/* Articles Section Skeleton */}
      <section className="border-t border-[#1A1A1A] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between animate-pulse">
            <div>
              <div className="h-8 w-48 bg-[#1A1A1A] rounded" />
              <div className="mt-1 h-4 w-56 bg-[#1A1A1A] rounded" />
            </div>
            <div className="h-9 w-24 bg-[#1A1A1A] rounded-lg" />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <ArticleCardSkeleton key={i} />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
