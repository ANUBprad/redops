/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  swcMinify: true,
  output: "standalone",
  experimental: {
    reactCompiler: true,
  },
};

export default config;
