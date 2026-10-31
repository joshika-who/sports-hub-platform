/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // When running locally on your computer (`npm run dev`), forward /api requests
    // to the local FastAPI backend on port 8000. On Vercel, vercel.json routes /api
    // directly to the Python serverless function on the same website.
    if (process.env.VERCEL) {
      return [];
    }
    const localBackend = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${localBackend}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${localBackend}/health`,
      },
      {
        source: "/uploads/:path*",
        destination: `${localBackend}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
