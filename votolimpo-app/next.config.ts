import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Server Actions enabled by default in Next.js 15
  },
};

export default nextConfig;
