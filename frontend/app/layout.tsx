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
