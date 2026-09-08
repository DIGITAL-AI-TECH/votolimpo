import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0A0A",
        foreground: "#FAFAFA",
        accent: {
          DEFAULT: "#10B981",
          50: "#ECFDF5",
          100: "#D1FAE5",
          200: "#A7F3D0",
          300: "#6EE7B7",
          400: "#34D399",
          500: "#10B981",
          600: "#059669",
          700: "#047857",
          800: "#065F46",
          900: "#064E3B",
        },
        surface: {
          DEFAULT: "#141414",
          100: "#1A1A1A",
          200: "#242424",
          300: "#2E2E2E",
        },
        muted: "#6B7280",
        border: "#2E2E2E",
        severity: {
          critical: "#EF4444",
          high: "#F97316",
          medium: "#EAB308",
          low: "#3B82F6",
          info: "#6B7280",
        },
        score: {
          excellent: "#10B981",
          good: "#3B82F6",
          fair: "#EAB308",
          poor: "#F97316",
          critical: "#EF4444",
        },
        party: {
          pt: "#FF0000",
          pl: "#002776",
          mdb: "#00A859",
          psdb: "#0066CC",
          pp: "#1e3a8a",
          psd: "#FFD700",
          republicanos: "#FF6600",
          psol: "#FF69B4",
          pcdob: "#CC0000",
          pdT: "#009B3A",
          solidariedade: "#FF8C00",
          avante: "#00B4D8",
          cidadania: "#FF4500",
          patriota: "#006400",
          pros: "#800080",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "hero-gradient":
          "radial-gradient(ellipse at center, #10B98115 0%, transparent 70%)",
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-in-out",
        "slide-up": "slideUp 0.3s ease-out",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
