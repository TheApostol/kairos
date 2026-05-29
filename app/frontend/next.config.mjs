/** @type {import('next').NextConfig} */
const config = {
  // Allow builds even with ESLint warnings
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
}

export default config
