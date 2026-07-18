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

};

export default nextConfig;
