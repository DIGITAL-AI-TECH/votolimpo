import { Card } from "@/components/ui/Card";
import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="max-w-md text-center">
        <p className="text-6xl font-bold text-[#FF5722]">404</p>
        <p className="mt-4 text-lg text-[#D4D8DD]">Pagina nao encontrada</p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block rounded-xl bg-[#FF5722] px-6 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#E64A19]"
        >
          Voltar ao Dashboard
        </Link>
      </Card>
    </div>
  );
}
