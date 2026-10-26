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
      // Fallback fallback so dashboard doesn't crash if backend is starting
      setHospital((prev) => prev ?? {
        id: "01b587a3-f471-4406-a1c6-4deb8dd44845",
        name: "MedNexa City Hospital",
        address: "12 Civil Lines, Jabalpur, Madhya Pradesh 482001",
        phone: "+917612400000",
        email: "reception@mednexa.example",
        opening_time: "09:00:00",
        closing_time: "20:00:00",
        timezone: "Asia/Kolkata",
        languages: ["en", "hi"],
        general_instructions: "Patients should arrive 15 minutes before their slot.",
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
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
