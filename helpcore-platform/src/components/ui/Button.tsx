import { cn } from "@/lib/cn";
import { ButtonHTMLAttributes, forwardRef } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-xl font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#FF5722]/50",
          {
            "bg-[#FF5722] text-white hover:bg-[#E64A19] shadow-[0_10px_30px_rgba(255,87,34,0.3)]":
              variant === "primary",
            "border border-[#FF5722] text-[#FF5722] hover:bg-[#FF5722] hover:text-white bg-transparent":
              variant === "outline",
            "text-[#9EA5AC] hover:text-white hover:bg-[#1A1A1A] bg-transparent":
              variant === "ghost",
          },
          {
            "px-3 py-1.5 text-sm": size === "sm",
            "px-4 py-2 text-sm": size === "md",
            "px-6 py-3 text-base": size === "lg",
          },
          "disabled:opacity-50 disabled:cursor-not-allowed",
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button };
