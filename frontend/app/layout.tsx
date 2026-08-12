import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Acrasystem Licitações",
  description: "Acompanhamento de licitações públicas",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
