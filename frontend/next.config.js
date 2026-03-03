/** @type {import('next').NextConfig} */

const isProd = process.env.NODE_ENV === 'production';

const nextConfig = {
  reactStrictMode: true,
  // 프로덕션: 정적 빌드 (FastAPI에서 서빙)
  // 개발: Next.js dev server의 rewrite 프록시 사용
  ...(isProd ? { output: 'export' } : {}),
  ...(!isProd ? {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: 'http://localhost:8001/api/:path*',
        },
        {
          source: '/ws/:path*',
          destination: 'http://localhost:8001/ws/:path*',
        },
      ];
    },
  } : {}),
};

module.exports = nextConfig;
