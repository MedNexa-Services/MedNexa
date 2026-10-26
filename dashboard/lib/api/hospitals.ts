import { apiClient } from "./client";
import type {
  HospitalOut,
  HospitalCreate,
  HospitalUpdate,
  HospitalInfoOut,
  HospitalInfoCreate,
  HospitalInfoUpdate,
  Page,
} from "./types";

export async function listHospitals(limit = 50, offset = 0): Promise<Page<HospitalOut>> {
  const res = await apiClient.get("/hospitals", { params: { limit, offset } });
  return res.data;
}

export async function getHospital(id: string): Promise<HospitalOut> {
  const res = await apiClient.get(`/hospitals/${id}`);
  return res.data;
}

export async function createHospital(data: HospitalCreate): Promise<HospitalOut> {
  const res = await apiClient.post("/hospitals", data);
  return res.data;
}

export async function updateHospital(id: string, data: HospitalUpdate): Promise<HospitalOut> {
  const res = await apiClient.patch(`/hospitals/${id}`, data);
  return res.data;
}

export async function listHospitalInfo(
  hospitalId: string,
  params: { category?: string; include_inactive?: boolean; limit?: number; offset?: number } = {}
): Promise<Page<HospitalInfoOut>> {
  const res = await apiClient.get(`/hospitals/${hospitalId}/info`, { params });
  return res.data;
}

export async function createHospitalInfo(
  hospitalId: string,
  data: HospitalInfoCreate
): Promise<HospitalInfoOut> {
  const res = await apiClient.post(`/hospitals/${hospitalId}/info`, data);
  return res.data;
}

export async function updateHospitalInfo(
  infoId: string,
  data: HospitalInfoUpdate
): Promise<HospitalInfoOut> {
  const res = await apiClient.patch(`/info/${infoId}`, data);
  return res.data;
}

export async function deleteHospitalInfo(infoId: string): Promise<void> {
  await apiClient.delete(`/info/${infoId}`);
}
