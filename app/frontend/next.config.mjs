/** @type {import('next').NextConfig} */
const config = {
  basePath: '/dashboard',
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/admin',
        permanent: false,
      },
      {
        source: '/platform',
        destination: '/admin',
        permanent: false,
      },
      {
        source: '/platform/:path*',
        destination: '/admin/:path*',
        permanent: false,
      },
    ]
  },
  async rewrites() {
    return [
      {
        source: '/admin',
        destination: '/platform',
      },
      {
        source: '/admin/:path*',
        destination: '/platform/:path*',
      },
    ]
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'd22fxaf9t8d39k.cloudfront.net' },
      { protocol: 'https', hostname: '*.cloudfront.net' },
    ],
    formats: ['image/webp', 'image/avif'],
    minimumCacheTTL: 86400,
  },
}

export default config
