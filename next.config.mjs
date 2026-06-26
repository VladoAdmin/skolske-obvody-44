import createMDX from '@next/mdx'

const withMDX = createMDX({ extension: /\.mdx?$/ })

/** @type {import('next').NextConfig} */
const nextConfig = {
  // MDX page extensions
  pageExtensions: ['ts', 'tsx', 'js', 'jsx', 'md', 'mdx'],

  // Strict mode for development
  reactStrictMode: true,

  // Webpack: allow MapLibre GL (uses worker threads)
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      // MapLibre workers need this alias for Next.js bundling
      "maplibre-gl": "maplibre-gl",
    };
    return config;
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
};

export default withMDX(nextConfig)
