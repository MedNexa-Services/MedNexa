"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Stethoscope,
  CalendarCheck2,
  Users,
  HelpCircle,
  PhoneCall,
  BarChart3,
  Settings,
  Bot,
  ExternalLink,
  HeartPulse,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  onClose?: () => void;
}

const navItems = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    badge: null,
  },
  {
    name: "Doctors",
    href: "/doctors",
    icon: Stethoscope,
    badge: null,
  },
  {
    name: "Appointments",
    href: "/appointments",
    icon: CalendarCheck2,
    badge: null,
  },
  {
    name: "Patients",
    href: "/patients",
    icon: Users,
    badge: null,
  },
  {
    name: "Hospital Info",
    href: "/hospital-info",
    icon: HelpCircle,
    badge: "AI FAQ",
  },
  {
    name: "Call Logs",
    href: "/call-logs",
    icon: PhoneCall,
    badge: "Live",
  },
  {
    name: "Analytics",
    href: "/analytics",
    icon: BarChart3,
    badge: null,
  },
  {
    name: "Settings",
    href: "/settings",
    icon: Settings,
    badge: null,
  },
];

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex flex-col h-full bg-sidebar border-r border-sidebar-border select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-sidebar-border">
        <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20">
          <HeartPulse className="w-6 h-6" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-lg text-sidebar-foreground tracking-tight">
              MedNexa
            </span>
            <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
              AI OS
            </span>
          </div>
          <span className="text-xs text-muted-foreground -mt-0.5">
            Hospital Admin
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
          Management
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                isActive
                  ? "bg-blue-600 text-white shadow-sm shadow-blue-600/20"
                  : "text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent"
              )}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Icon
                  className={cn(
                    "w-4 h-4 shrink-0 transition-colors",
                    isActive
                      ? "text-white"
                      : "text-muted-foreground group-hover:text-sidebar-foreground"
                  )}
                />
                <span className="truncate">{item.name}</span>
              </div>

              {item.badge && (
                <span
                  className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded-full font-semibold shrink-0 uppercase tracking-wide",
                    isActive
                      ? "bg-white/20 text-white"
                      : item.badge === "Live"
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* AI & System Status Footer */}
      <div className="p-3 border-t border-sidebar-border bg-sidebar/50 space-y-2">
        <div className="p-3 rounded-lg border border-sidebar-border bg-card/60 backdrop-blur-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-sidebar-foreground">
              <Bot className="w-3.5 h-3.5 text-blue-500" />
              <span>AI Receptionist</span>
            </div>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Active
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Ready for incoming bilingual calls via local AI stack.
          </p>
        </div>

        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <span>FastAPI Docs</span>
            <span className="text-[10px] px-1 py-0.2 bg-muted rounded font-mono">v1</span>
          </span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </aside>
  );
}
