"use client";

import { ErrorBoundary } from "@/components/error-boundary";

export default function RootLayoutError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorBoundary error={error} reset={reset} />;
}
