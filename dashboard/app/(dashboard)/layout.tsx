"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useAuth } from "@/contexts/AuthContext";
import { useHospital } from "@/contexts/HospitalContext";
import { X, HeartPulse, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  const { error: hospitalError, refreshHospital } = useHospital();
  const router = useRouter();

  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);
  const [offlineBannerDismissed, setOfflineBannerDismissed] = React.useState(false);
  const [isRetrying, setIsRetrying] = React.useState(false);

  // Authentication gate: redirect unauthenticated users to /login
  React.useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  const handleRetryBackend = async () => {
    setIsRetrying(true);
    try {
      await refreshHospital();
      setOfflineBannerDismissed(false);
    } finally {
      setIsRetrying(false);
    }
  };

  // Loading state while verifying auth session
  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-3">
        <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/25 animate-bounce">
          <HeartPulse className="w-6 h-6" />
        </div>
        <p className="text-sm font-medium text-muted-foreground animate-pulse">
          Authenticating hospital staff session...
        </p>
      </div>
    );
  }

  // If not authenticated, do not render children while redirect happens
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden">
      {/* Desktop Persistent Sidebar */}
      <div className="hidden md:flex h-full shrink-0">
        <Sidebar />
      </div>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer content */}
          <div className="relative flex flex-col h-full z-10 w-72 max-w-[85vw] shadow-2xl animate-in slide-in-from-left duration-200">
            <Sidebar onClose={() => setMobileMenuOpen(false)} />
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="absolute top-4 right-3 p-1.5 rounded-lg bg-sidebar-accent text-sidebar-foreground hover:bg-muted cursor-pointer"
              aria-label="Close navigation"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        <TopBar onMenuClick={() => setMobileMenuOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto w-full">
            {/* Global Backend Offline Banner */}
            {hospitalError && !offlineBannerDismissed && (
              <div className="mb-4 p-3 rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-xs">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>
                    <strong>Backend unreachable:</strong> {hospitalError}. Data on this page may be missing or out of date.
                  </span>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleRetryBackend}
                    disabled={isRetrying}
                    className="h-7 px-2 text-[11px] border-amber-500/30 text-amber-800 dark:text-amber-300 hover:bg-amber-500/20 cursor-pointer"
                  >
                    <RefreshCw className={`w-3 h-3 mr-1 ${isRetrying ? "animate-spin" : ""}`} />
                    <span>Retry Connection</span>
                  </Button>
                  <button
                    type="button"
                    onClick={() => setOfflineBannerDismissed(true)}
                    className="p-1 hover:bg-amber-500/20 rounded text-amber-700 dark:text-amber-400 cursor-pointer"
                    aria-label="Dismiss banner"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}

            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
