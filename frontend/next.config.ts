import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lean, self-contained build output for the Docker image (no need to
  // ship node_modules — see frontend/Dockerfile). NOT for Vercel: Vercel
  // has its own serverless bundling, and combining the two breaks its
  // post-build trace step (ENOENT on a .nft.json file) — Vercel sets its
  // own VERCEL env var during builds, so skip standalone mode there.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
};

export default nextConfig;
