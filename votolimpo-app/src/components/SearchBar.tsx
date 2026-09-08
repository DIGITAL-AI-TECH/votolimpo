"use client";

import { useRouter } from "next/navigation";
import { useState, type FC, type FormEvent } from "react";

interface SearchBarProps {
  placeholder?: string;
  defaultValue?: string;
  onSearch?: (query: string) => void;
  className?: string;
}

const SearchBar: FC<SearchBarProps> = ({
  placeholder = "Buscar político, partido ou UF...",
  defaultValue = "",
  onSearch,
  className = "",
}) => {
  const router = useRouter();
  const [value, setValue] = useState(defaultValue);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (onSearch) {
      onSearch(value);
    } else {
      router.push(`/busca?q=${encodeURIComponent(value)}`);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={`relative ${className}`}>
      <div className="relative">
        <svg
          className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#6B7280]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-[#2E2E2E] bg-[#141414] py-3.5 pl-12 pr-24 text-[#FAFAFA] placeholder-[#6B7280] outline-none transition-all focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 text-sm"
          autoComplete="off"
        />
        <button
          type="submit"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 active:bg-emerald-700"
        >
          Buscar
        </button>
      </div>
    </form>
  );
};

export default SearchBar;
