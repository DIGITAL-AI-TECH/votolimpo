"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/browse", label: "Browse" },
  { href: "/articles", label: "Busca" },
  { href: "/review", label: "Revisão" },
];

export function Navbar() {
  const pathname = usePathname();

  // Don't show navbar on login page
  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-50 border-b border-[#1F1F1F] bg-black/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <Link href="/dashboard" className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://elloconsultoria.com/images/ello-logo-orange.png"
            alt="Ello Consultoria"
            className="h-8"
          />
          <span className="text-sm font-bold text-white">Help Core</span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-[#FF5722]/10 text-[#FF5722]"
                    : "text-[#9EA5AC] hover:text-white"
                )}
              >
                {item.label}
              </Link>
            );
          })}

          <form action="/api/auth/logout" method="POST" className="ml-4">
            <button
              type="submit"
              className="rounded-lg px-3 py-1.5 text-sm text-[#9EA5AC] hover:text-white transition-colors"
            >
              Sair
            </button>
          </form>
        </nav>
      </div>
    </header>
  );
}
