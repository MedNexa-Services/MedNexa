"use client";

import * as React from "react";
import { listHospitals, type HospitalOut } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface HospitalContextType {
  hospital: HospitalOut | null;
  hospitalId: string | undefined;
  isLoading: boolean;
  needsSetup: boolean;
  error: string | null;
  refreshHospital: () => Promise<void>;
}

const HospitalContext = React.createContext<HospitalContextType | undefined>(undefined);

export function HospitalProvider({ children }: { children: React.ReactNode }) {
  const [hospital, setHospital] = React.useState<HospitalOut | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [needsSetup, setNeedsSetup] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const fetchActiveHospital = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const page = await listHospitals(1, 0);
      setHospital(page.items[0] ?? null);
      setNeedsSetup(page.items.length === 0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load hospital data";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const { isAuthenticated } = useAuth();
  React.useEffect(() => {
    if (isAuthenticated) {
      fetchActiveHospital();
    } else {
      setHospital(null);
      setNeedsSetup(false);
      setError(null);
    }
  }, [isAuthenticated, fetchActiveHospital]);

  return (
    <HospitalContext.Provider
      value={{
        hospital,
        hospitalId: hospital?.id,
        isLoading,
        needsSetup,
        error,
        refreshHospital: fetchActiveHospital,
      }}
    >
      {children}
    </HospitalContext.Provider>
  );
}

export function useHospital() {
  const context = React.useContext(HospitalContext);
  if (!context) {
    throw new Error("useHospital must be used within a HospitalProvider");
  }
  return context;
}
