"use client";

import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Home, Search, RotateCcw, ExternalLink } from "lucide-react";

export default function NotFound() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <div className="mb-8">
          <span className="text-9xl font-bold text-muted-foreground/30">404</span>
        </div>
        <h1 className="mb-4 text-3xl font-bold">Page Not Found</h1>
        <p className="mx-auto mb-8 max-w-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has been moved. It might have been
          a temporary evaluation run that was deleted, or the URL was mistyped.
        </p>
        <div className="flex flex-col justify-center gap-4 sm:flex-row">
          <Link href={user ? "/dashboard" : "/"} className="w-full sm:w-auto">
            <Button size="lg" className="gap-2">
              <Home className="h-4 w-4" />
              {user ? "Back to Dashboard" : "Go Home"}
            </Button>
          </Link>
          {!user && (
            <Link href="/register" className="w-full sm:w-auto">
              <Button size="lg" variant="outline" className="gap-2">
                <Search className="h-4 w-4" />
                Create Account
              </Button>
            </Link>
          )}
        </div>
        <div className="mt-12 border-t border-border pt-8">
          <div className="grid gap-4 text-center sm:grid-cols-3">
            <Link
              href="/login"
              className="flex items-center justify-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <RotateCcw className="h-4 w-4" />
              Sign In
            </Link>
            <Link
              href="/register"
              className="flex items-center justify-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" />
              Register
            </Link>
            <a
              href="https://github.com/ANUBprad/redops"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" />
              GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
