import { apiClient } from "./client";
import type { PatientOut, PatientCreate, PatientUpdate, AppointmentOut, Page } from "./types";

export async function searchPatients(params: {
  hospital_id?: string;
  phone?: string;
  name?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<Page<PatientOut>> {
  const res = await apiClient.get("/patients", { params });
  return res.data;
}

export async function getPatient(id: string): Promise<PatientOut> {
  const res = await apiClient.get(`/patients/${id}`);
  return res.data;
}

export async function createPatient(data: PatientCreate): Promise<PatientOut> {
  const res = await apiClient.post("/patients", data);
  return res.data;
}

export async function updatePatient(id: string, data: PatientUpdate): Promise<PatientOut> {
  const res = await apiClient.patch(`/patients/${id}`, data);
  return res.data;
}

export async function getPatientAppointments(
  patientId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<Page<AppointmentOut>> {
  const res = await apiClient.get(`/patients/${patientId}/appointments`, { params });
  return res.data;
}
