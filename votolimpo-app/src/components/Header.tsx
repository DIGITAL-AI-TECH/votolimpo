"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { FC } from "react";

const NAV_LINKS = [
  { href: "/", label: "Início" },
  { href: "/ranking", label: "Ranking" },
  { href: "/busca", label: "Busca" },
  { href: "/grafo", label: "Grafo" },
];

const Header: FC = () => {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-[#2E2E2E] bg-[#0A0A0A]/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2 group"
          aria-label="Voto Limpo — Página inicial"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/30 group-hover:bg-emerald-500/20 transition-colors">
            <svg
              className="h-4 w-4 text-emerald-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <span className="text-lg font-bold tracking-tight text-[#FAFAFA]">
            Voto<span className="text-emerald-400">Limpo</span>
          </span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-[#6B7280] hover:bg-[#1A1A1A] hover:text-[#FAFAFA]"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Mobile nav button */}
        <div className="flex md:hidden">
          <Link
            href="/busca"
            className="rounded-lg p-2 text-[#6B7280] hover:bg-[#1A1A1A] hover:text-[#FAFAFA] transition-colors"
            aria-label="Buscar"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </Link>
        </div>

        {/* Mobile bottom nav hint */}
        <div className="hidden">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </div>
      </div>

      {/* Mobile navigation */}
      <div className="md:hidden border-t border-[#1A1A1A]">
        <div className="flex items-center gap-1 px-4 py-2 overflow-x-auto">
          {NAV_LINKS.map((link) => {
            const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex-shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-[#6B7280] hover:text-[#FAFAFA]"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
    </header>
  );
};

export default Header;
