"use client";

import * as React from "react";
import { AlertTriangle, RefreshCw, Home, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import Link from "next/link";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    console.error("Dashboard error caught by boundary:", error);
  }, [error]);

  return (
    <div className="min-h-[500px] flex items-center justify-center p-4">
      <Card className="max-w-md w-full p-6 text-center space-y-4 border-destructive/30 bg-card shadow-lg">
        <div className="w-14 h-14 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center mx-auto">
          <ShieldAlert className="w-7 h-7" />
        </div>

        <div>
          <h2 className="text-lg font-bold text-foreground">Something went wrong</h2>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {error.message || "An unexpected error occurred while loading this dashboard view."}
          </p>
          {error.digest && (
            <p className="text-[10px] font-mono text-muted-foreground/70 mt-1">
              Error Digest: {error.digest}
            </p>
          )}
        </div>

        <div className="p-3 bg-muted/40 rounded-lg text-left text-[11px] text-muted-foreground space-y-1">
          <span className="font-semibold block text-foreground">Suggested Troubleshooting:</span>
          <ul className="list-disc list-inside space-y-0.5">
            <li>Verify the backend is running and the dashboard server&apos;s <code>BACKEND_URL</code> points to it</li>
            <li>Check network connectivity or reload the page</li>
          </ul>
        </div>

        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => reset()}
            className="gap-1.5 cursor-pointer text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Try Again</span>
          </Button>

          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center h-8 px-3 rounded-md text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors gap-1.5"
          >
            <Home className="w-3.5 h-3.5" />
            <span>Back to Home</span>
          </Link>
        </div>
      </Card>
    </div>
  );
}
