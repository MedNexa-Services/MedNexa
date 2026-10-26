import { apiClient } from "./client";
import type { SlotOut, DoctorSlotOut } from "./types";

export async function getDoctorSlots(doctorId: string, date: string): Promise<SlotOut[]> {
  const res = await apiClient.get(`/doctors/${doctorId}/slots`, { params: { date } });
  return res.data;
}

export async function getNextAvailableSlots(params: {
  hospital_id: string;
  speciality: string;
  from?: string;
  limit?: number;
}): Promise<DoctorSlotOut[]> {
  const res = await apiClient.get("/slots/next-available", { params });
  return res.data;
}
