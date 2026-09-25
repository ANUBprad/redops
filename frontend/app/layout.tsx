import "@/styles/globals.css";
import { type ReactNode } from "react";
import { Providers } from "@/providers/providers";
import { Toaster } from "sonner";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "RedOps Eval",
  description: "Production-grade LLM Evaluation & Red Teaming Platform",
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
