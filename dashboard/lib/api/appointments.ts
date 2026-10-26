import { apiClient } from "./client";
import type {
  AppointmentOut,
  BookingRequest,
  BookingConfirmation,
  CancelRequest,
  RescheduleRequest,
  AppointmentStatus,
  Page,
} from "./types";

export async function listAppointments(params: {
  hospital_id?: string;
  doctor_id?: string;
  patient_id?: string;
  date?: string;
  date_from?: string;
  date_to?: string;
  status?: AppointmentStatus;
  limit?: number;
  offset?: number;
} = {}): Promise<Page<AppointmentOut>> {
  const res = await apiClient.get("/appointments", { params });
  return res.data;
}

export async function getAppointment(id: string): Promise<AppointmentOut> {
  const res = await apiClient.get(`/appointments/${id}`);
  return res.data;
}

export async function bookAppointment(data: BookingRequest): Promise<BookingConfirmation> {
  const res = await apiClient.post("/appointments", data);
  return res.data;
}

export async function cancelAppointment(id: string, data: CancelRequest): Promise<AppointmentOut> {
  const res = await apiClient.post(`/appointments/${id}/cancel`, data);
  return res.data;
}

export async function rescheduleAppointment(
  id: string,
  data: RescheduleRequest
): Promise<BookingConfirmation> {
  const res = await apiClient.post(`/appointments/${id}/reschedule`, data);
  return res.data;
}
