import { cn } from "@/lib/cn";
import { HTMLAttributes } from "react";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "critical" | "high" | "medium" | "low";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        {
          "bg-[#1A1A1A] text-[#D4D8DD] border border-[#1F1F1F]":
            variant === "default",
          "bg-red-500/20 text-red-400 border border-red-500/30":
            variant === "critical",
          "bg-orange-500/20 text-orange-400 border border-orange-500/30":
            variant === "high",
          "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30":
            variant === "medium",
          "bg-green-500/20 text-green-400 border border-green-500/30":
            variant === "low",
        },
        className
      )}
      {...props}
    />
  );
}
