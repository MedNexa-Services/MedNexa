import { apiClient } from "./client";
import type { CallSessionOut, CallSessionDetailOut, CallOutcome, Page } from "./types";

export async function listCalls(params: {
  hospital_id?: string;
  caller_phone?: string;
  outcome?: CallOutcome;
  escalated?: boolean;
  started_after?: string;
  started_before?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<Page<CallSessionOut>> {
  const res = await apiClient.get("/calls", { params });
  return res.data;
}

export async function getCall(sessionId: string): Promise<CallSessionDetailOut> {
  const res = await apiClient.get(`/calls/${sessionId}`);
  return res.data;
}
