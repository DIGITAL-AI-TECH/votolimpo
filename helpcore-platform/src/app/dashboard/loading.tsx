import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

export default function DashboardLoading() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-10 w-32" />
          </Card>
        ))}
      </div>
      <Card>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-4 h-8 w-full" />
      </Card>
      <Card>
        <Skeleton className="h-6 w-56" />
        <Skeleton className="mt-4 h-[400px] w-full" />
      </Card>
    </div>
  );
}
