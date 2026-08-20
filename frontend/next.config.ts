import type { NextConfig } from "next";

const BACKEND_ORIGIN = "http://8.231.72.145:8000";

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

  // Security headers
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

  // Reverse proxy: /api/hearbeat/:path* → GCP backend /:path*
  async rewrites() {
    return [
      {
        source: "/api/hearbeat/:path*",
        destination: `${BACKEND_ORIGIN}/:path*`,
      },
    ];
  },
};

export default nextConfig;
