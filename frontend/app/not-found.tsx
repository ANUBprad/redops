"use client";

import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Home, Search, RotateCcw, ExternalLink } from "lucide-react";

export default function NotFound() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <div className="mb-8">
          <span className="text-9xl font-bold text-muted-foreground/30">404</span>
        </div>
        <h1 className="text-3xl font-bold mb-4">Page Not Found</h1>
        <p className="text-muted-foreground mb-8 max-w-sm mx-auto">
          The page you're looking for doesn't exist or has been moved. It might have been a temporary evaluation run that was deleted, or the URL was mistyped.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
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
        <div className="mt-12 pt-8 border-t border-border">
          <div className="grid gap-4 sm:grid-cols-3 text-center">
            <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1">
              <RotateCcw className="h-4 w-4" />
              Sign In
            </Link>
            <Link href="/register" className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1">
              <ExternalLink className="h-4 w-4" />
              Register
            </Link>
            <a href="https://github.com/ANUBprad/redops" target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1">
              <ExternalLink className="h-4 w-4" />
              GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}