import type { NextConfig } from "next";

// In development the calculator's Python API runs on its own port (npm run api); on Vercel /api/*.py are functions of the same project.
const nextConfig: NextConfig = {
  async rewrites() {
    return process.env.NODE_ENV === "production" && !process.env.LOCAL_API
      ? []
      : [{ source: "/api/:path*", destination: "http://127.0.0.1:8765/api/:path*" }];
  },
};

export default nextConfig;
