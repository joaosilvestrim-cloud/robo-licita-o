/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // NEXT_PUBLIC_API_URL vem do ambiente (Vercel). Aponta pra URL do backend no Render.
  // Ex.: https://robo-licitacao-api.onrender.com
  // Em dev local, se vazio, o front chama a mesma origem.
};

module.exports = nextConfig;
