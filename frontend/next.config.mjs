/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'hswcvugpdlkwaairkqyj.supabase.co',
      },
    ],
  },
};

export default nextConfig;
