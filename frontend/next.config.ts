import type { NextConfig } from "next";

const DEFAULT_LOCAL_BACKEND_URL = "http://localhost:8000";
const DEFAULT_PRODUCTION_BACKEND_URL = "https://fortressflow-api.vercel.app";

function getBackendUrl(): string {
  const configuredUrl =
    process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;

  if (configuredUrl) {
    return configuredUrl.replace(/\/+$/, "");
  }

  return process.env.NODE_ENV === "production"
    ? DEFAULT_PRODUCTION_BACKEND_URL
    : DEFAULT_LOCAL_BACKEND_URL;
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  experimental: {
    missingSuspenseWithCSRFallback: false,
  },
  async rewrites() {
    const backend = getBackendUrl();

    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
