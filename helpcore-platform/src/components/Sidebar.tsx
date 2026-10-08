"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

interface SidebarArea {
  area: string;
  count: number;
  processed: number;
}

interface SidebarProps {
  areas: SidebarArea[];
}

export function Sidebar({ areas }: SidebarProps) {
  const pathname = usePathname();

  return (
    <nav className="w-64 shrink-0 overflow-y-auto border-r border-[#1F1F1F] bg-[#0A0A0A] p-4">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-[#9EA5AC]">
        Áreas Operacionais
      </h2>
      <ul className="space-y-1">
        {areas.map((a) => {
          const href = `/browse/${encodeURIComponent(a.area)}`;
          const isActive = pathname === href;

          return (
            <li key={a.area}>
              <Link
                href={href}
                className={cn(
                  "flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-[#FF5722]/10 text-[#FF5722] font-semibold"
                    : "text-[#D4D8DD] hover:bg-[#1A1A1A]"
                )}
              >
                <span className="truncate">{a.area}</span>
                <span className={cn(
                  "ml-2 shrink-0 text-xs",
                  isActive ? "text-[#FF5722]" : "text-[#9EA5AC]"
                )}>
                  {a.count.toLocaleString("pt-BR")}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
