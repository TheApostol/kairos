/** @type {import('next').NextConfig} */
const config = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
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
