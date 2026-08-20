/**
 * Central API configuration.
 *
 * Production (Vercel):  /api/hearbeat  (proxied to GCP backend via next.config.ts rewrites)
 * Development (local):  http://localhost:8000  (direct to backend)
 */

const isProd = process.env.NODE_ENV === "production";

export const API_BASE = isProd
  ? "/api/hearbeat"
  : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");
