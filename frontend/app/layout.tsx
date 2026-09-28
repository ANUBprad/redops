import "@/styles/globals.css";
import { type ReactNode } from "react";
import { Providers } from "@/providers/providers";
import { Toaster } from "sonner";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: {
    default: "RedOps Eval",
    template: "%s | RedOps Eval",
  },
  description: "Production-grade LLM Evaluation & Red Teaming Platform",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
  openGraph: {
    siteName: "RedOps",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    site: "@redops",
  },
  robots: {
    index: true,
    follow: true,
  },
};

// Nonce-based CSP (applied in middleware.ts) requires request-time rendering:
// statically prerendered HTML cannot receive the per-request nonce.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body className="bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
