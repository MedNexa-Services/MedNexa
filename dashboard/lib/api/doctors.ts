import { apiClient } from "./client";
import type {
  DoctorOut,
  DoctorDetailOut,
  DoctorCreate,
  DoctorUpdate,
  ScheduleOverrideOut,
  ScheduleOverrideIn,
  SlotOut,
  DoctorSlotOut,
  Page,
} from "./types";

export async function listDoctors(params: {
  hospital_id?: string;
  speciality?: string;
  department?: string;
  include_inactive?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<Page<DoctorOut>> {
  const res = await apiClient.get("/doctors", { params });
  return res.data;
}

export async function getDoctor(id: string): Promise<DoctorDetailOut> {
  const res = await apiClient.get(`/doctors/${id}`);
  return res.data;
}

export async function createDoctor(data: DoctorCreate): Promise<DoctorOut> {
  const res = await apiClient.post("/doctors", data);
  return res.data;
}

export async function updateDoctor(id: string, data: DoctorUpdate): Promise<DoctorOut> {
  const res = await apiClient.patch(`/doctors/${id}`, data);
  return res.data;
}

export async function deleteDoctor(id: string): Promise<void> {
  await apiClient.delete(`/doctors/${id}`);
}

export async function listScheduleOverrides(
  doctorId: string,
  params: { from?: string; to?: string } = {}
): Promise<ScheduleOverrideOut[]> {
  const res = await apiClient.get(`/doctors/${doctorId}/schedule`, { params });
  return res.data;
}

export async function upsertScheduleOverride(
  doctorId: string,
  data: ScheduleOverrideIn
): Promise<ScheduleOverrideOut> {
  const res = await apiClient.put(`/doctors/${doctorId}/schedule`, data);
  return res.data;
}

export async function deleteScheduleOverride(doctorId: string, on: string): Promise<void> {
  await apiClient.delete(`/doctors/${doctorId}/schedule/${on}`);
}
