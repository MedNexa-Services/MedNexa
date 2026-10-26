"use client";

import { Menu, Building2, Calendar, ShieldCheck, LogOut } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { useHospital } from "@/contexts/HospitalContext";
import { useAuth } from "@/contexts/AuthContext";

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { hospital, isLoading: isHospitalLoading } = useHospital();
  const { user, logout } = useAuth();

  const todayFormatted = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date());

  const hospitalName = hospital?.name ?? "City Care Hospital";

  return (
    <header className="h-16 border-b border-border bg-card/80 backdrop-blur-md sticky top-0 z-30 px-4 md:px-6 flex items-center justify-between">
      {/* Left side: Hamburger + Hospital Name from Context */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="md:hidden p-2 rounded-lg border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="hidden sm:flex w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 items-center justify-center text-blue-600 dark:text-blue-400">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-sm md:text-base text-foreground leading-none">
                {isHospitalLoading ? (
                  <span className="inline-block w-32 h-4 bg-muted animate-pulse rounded" />
                ) : (
                  hospitalName
                )}
              </h1>
              <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                Live OPD
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 hidden sm:block">
              {hospital?.address ? hospital.address.split(",")[0] : "Primary Hospital Facility"}
            </p>
          </div>
        </div>
      </div>

      {/* Right side: Date, Theme Toggle, User Profile & Logout */}
      <div className="flex items-center gap-2 sm:gap-3 md:gap-4">
        {/* Date display */}
        <div className="hidden lg:flex items-center gap-2 text-xs font-medium text-muted-foreground px-3 py-1.5 rounded-lg border border-border bg-background/50">
          <Calendar className="w-3.5 h-3.5 text-blue-500" />
          <span>{todayFormatted}</span>
        </div>

        {/* Dark Mode Toggle */}
        <ThemeToggle />

        {/* User / Staff Profile */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-border">
          <div className="w-8 h-8 md:w-9 md:h-9 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center font-bold text-xs shadow-xs ring-2 ring-background">
            AD
          </div>
          <div className="hidden md:block text-left">
            <div className="flex items-center gap-1 text-xs font-semibold text-foreground">
              <span>{user?.name ?? "Dr. Admin"}</span>
              <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
            </div>
            <p className="text-[11px] text-muted-foreground">{user?.role ?? "Staff"}</p>
          </div>

          {/* Logout Button */}
          <button
            type="button"
            onClick={logout}
            className="p-2 rounded-lg border border-border bg-card hover:bg-destructive/10 hover:border-destructive/30 hover:text-destructive text-muted-foreground transition-colors cursor-pointer ml-1"
            title="Sign out of staff portal"
            aria-label="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
