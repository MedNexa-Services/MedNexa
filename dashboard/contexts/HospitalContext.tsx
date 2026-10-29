"use client";

import * as React from "react";
import { listHospitals, type HospitalOut } from "@/lib/api";

interface HospitalContextType {
  hospital: HospitalOut | null;
  hospitalId: string | undefined;
  isLoading: boolean;
  error: string | null;
  refreshHospital: () => Promise<void>;
}

const HospitalContext = React.createContext<HospitalContextType | undefined>(undefined);

export function HospitalProvider({ children }: { children: React.ReactNode }) {
  const [hospital, setHospital] = React.useState<HospitalOut | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const fetchActiveHospital = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const page = await listHospitals(1, 0);
      if (page.items && page.items.length > 0) {
        setHospital(page.items[0]);
      } else {
        setError("No active hospital found in the database.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load hospital data";
      setError(msg);
      // Keep the last hospital actually loaded (if any); never substitute invented data.
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchActiveHospital();
  }, [fetchActiveHospital]);

  return (
    <HospitalContext.Provider
      value={{
        hospital,
        hospitalId: hospital?.id,
        isLoading,
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
