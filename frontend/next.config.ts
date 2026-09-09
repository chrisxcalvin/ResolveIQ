import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lean, self-contained build output for the Docker image (no need to
  // ship node_modules — see frontend/Dockerfile).
  output: "standalone",
};

export default nextConfig;
