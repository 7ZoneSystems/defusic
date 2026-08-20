import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev only: allow LAN access
  ...(process.env.NODE_ENV === "development"
    ? { allowedDevOrigins: ["192.168.1.185"] }
    : {}),

  // Production settings
  poweredByHeader: false,
  reactStrictMode: true,

  // Image optimization
  images: {
    formats: ["image/avif", "image/webp"],
  },

  // Headers for CORS (backend API calls)
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
