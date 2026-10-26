"use client";

import * as React from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/contexts/AuthContext";
import { HospitalProvider } from "@/contexts/HospitalContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <AuthProvider>
        <HospitalProvider>
          {children}
        </HospitalProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
