"use client";

import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="max-w-md text-center">
        <p className="text-4xl font-bold text-[#FF5722]">Erro</p>
        <p className="mt-4 text-[#D4D8DD]">
          {error.message || "Ocorreu um erro inesperado."}
        </p>
        <Button className="mt-6" onClick={reset}>
          Tentar novamente
        </Button>
      </Card>
    </div>
  );
}
