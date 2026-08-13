import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sonar · por Drive Data",
  description: "Sonar — monitore licitações públicas em todo o Brasil. Por Drive Data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
