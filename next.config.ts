import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  allowedDevOrigins: ['*.dev.coze.site'],
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'lf-coze-web-cdn.coze.cn',
        pathname: '/**',
      },
    ],
  },
  logging: {
    fetches: {
      fullUrl: false,
    },
  },
  // Turbopack配置（Next.js 16默认使用Turbopack）
  turbopack: {},
  // 防止HTML被缓存，确保每次rebuild后浏览器获取最新HTML（引用正确的chunk哈希）
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate, proxy-revalidate',
          },
        ],
      },
      {
        // 静态资源（带哈希的chunk）可以长期缓存，因为内容变化时哈希会变
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
