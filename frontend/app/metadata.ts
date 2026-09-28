import { Metadata } from "next";

export const metadata: Metadata = {
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