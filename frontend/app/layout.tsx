import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Drive Data · Licitações",
  description: "Monitore licitações públicas em todo o Brasil — por Drive Data",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
