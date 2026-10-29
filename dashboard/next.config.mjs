/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return {
      // La landing (FR/AR, design d'origine) est servie à la racine.
      beforeFiles: [{ source: "/", destination: "/landing.html" }],
      afterFiles: [],
      fallback: [],
    };
  },
};

export default nextConfig;
