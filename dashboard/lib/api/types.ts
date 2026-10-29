// ─── Enums ────────────────────────────────────────────────────────────────────
export type AppointmentStatus =
  | "BOOKED"
  | "CANCELLED"
  | "COMPLETED"
  | "NO_SHOW"
  | "RESCHEDULED";

export type BookingSource = "AI_CALL" | "DASHBOARD" | "WALK_IN";

export type CallOutcome =
  | "BOOKED"
  | "CANCELLED"
  | "RESCHEDULED"
  | "INFO_PROVIDED"
  | "ESCALATED"
  | "ABANDONED"
  | "OTHER";

export type CallRole = "USER" | "ASSISTANT" | "TOOL" | "SYSTEM";
export type Gender = "MALE" | "FEMALE" | "OTHER";

// ─── Pagination wrapper ───────────────────────────────────────────────────────
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ─── Hospital ─────────────────────────────────────────────────────────────────
export interface HospitalOut {
  id: string;
  name: string;
  address: string;
  phone: string;
  email: string | null;
  opening_time: string;
  closing_time: string;
  timezone: string;
  languages: string[];
  general_instructions: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HospitalCreate {
  name: string;
  address: string;
  phone: string;
  email?: string | null;
  opening_time: string;
  closing_time: string;
  timezone?: string;
  languages?: string[];
  general_instructions?: string | null;
}

export interface HospitalUpdate {
  name?: string | null;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  opening_time?: string | null;
  closing_time?: string | null;
  timezone?: string | null;
  languages?: string[] | null;
  general_instructions?: string | null;
  is_active?: boolean | null;
}

// ─── Hospital Info ─────────────────────────────────────────────────────────────
export interface HospitalInfoOut {
  id: string;
  hospital_id: string;
  category: string;
  question: string;
  answer: string;
  is_active: boolean;
  updated_at: string;
}

export interface HospitalInfoCreate {
  category: string;
  question: string;
  answer: string;
}

export interface HospitalInfoUpdate {
  category?: string | null;
  question?: string | null;
  answer?: string | null;
  is_active?: boolean | null;
}

// ─── Doctor ───────────────────────────────────────────────────────────────────
export interface DoctorOut {
  id: string;
  hospital_id: string;
  name: string;
  speciality: string;
  qualification: string | null;
  department: string;
  max_daily_appointments: number;
  slot_duration_minutes: number;
  available_days: number[];
  slot_start_time: string;
  slot_end_time: string;
  is_active: boolean;
  bio: string | null;
  created_at: string;
  updated_at: string;
}

export interface DoctorDetailOut extends DoctorOut {
  upcoming_overrides: ScheduleOverrideOut[];
}

export interface DoctorCreate {
  hospital_id: string;
  name: string;
  speciality: string;
  qualification?: string | null;
  department: string;
  max_daily_appointments: number;
  slot_duration_minutes: number;
  available_days: number[];
  slot_start_time: string;
  slot_end_time: string;
  bio?: string | null;
}

export interface DoctorUpdate {
  name?: string | null;
  speciality?: string | null;
  qualification?: string | null;
  department?: string | null;
  max_daily_appointments?: number | null;
  slot_duration_minutes?: number | null;
  available_days?: number[] | null;
  slot_start_time?: string | null;
  slot_end_time?: string | null;
  is_active?: boolean | null;
  bio?: string | null;
}

// ─── Schedule Override ────────────────────────────────────────────────────────
export interface ScheduleOverrideOut {
  id: string;
  doctor_id: string;
  date: string;
  is_available: boolean;
  start_time: string | null;
  end_time: string | null;
  override_reason: string | null;
}

export interface ScheduleOverrideIn {
  date: string;
  is_available: boolean;
  start_time?: string | null;
  end_time?: string | null;
  override_reason?: string | null;
}

// ─── Slot ─────────────────────────────────────────────────────────────────────
export interface SlotOut {
  start: string;
  end: string;
}

export interface DoctorSlotOut {
  doctor_id: string;
  doctor_name: string;
  speciality: string;
  department: string;
  date: string;
  start: string;
  end: string;
}

// ─── Patient ──────────────────────────────────────────────────────────────────
export interface PatientOut {
  id: string;
  hospital_id: string;
  name: string;
  phone: string;
  age: number | null;
  gender: Gender | null;
  email: string | null;
  address: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatientIn {
  name: string;
  phone: string;
  age?: number | null;
  gender?: Gender | null;
  email?: string | null;
  address?: string | null;
}

export interface PatientCreate extends PatientIn {
  hospital_id: string;
}

// Name and phone identify a patient and cannot be changed through the API.
export interface PatientUpdate {
  age?: number | null;
  gender?: Gender | null;
  email?: string | null;
  address?: string | null;
}

// ─── Appointment ──────────────────────────────────────────────────────────────
export interface AppointmentOut {
  id: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  doctor_id: string;
  doctor_name: string;
  department: string;
  hospital_id: string;
  appointment_date: string;
  appointment_time: string;
  slot_duration_minutes: number;
  status: AppointmentStatus;
  booking_source: BookingSource;
  token_number: number;
  notes: string | null;
  rescheduled_from_id: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
}

export interface BookingRequest {
  patient: PatientIn;
  doctor_id: string;
  appointment_date: string;
  appointment_time: string;
  notes?: string | null;
  booking_source?: BookingSource;
}

export interface BookingConfirmation {
  appointment_id: string;
  token_number: number;
  patient_name: string;
  doctor_name: string;
  department: string;
  appointment_date: string;
  appointment_time: string;
  status: AppointmentStatus;
}

export interface CancelRequest {
  reason?: string | null;
}

export interface RescheduleRequest {
  new_date: string;
  new_time: string;
}

// ─── Call ─────────────────────────────────────────────────────────────────────
export interface CallSessionOut {
  id: string;
  hospital_id: string;
  caller_phone: string;
  call_start: string;
  call_end: string | null;
  language_detected: string | null;
  call_outcome: CallOutcome | null;
  summary: string | null;
  escalated_to_human: boolean;
  total_turns: number;
}

export interface CallLogOut {
  id: string;
  session_id: string;
  appointment_id: string | null;
  role: CallRole;
  content: string;
  tool_called: string | null;
  tool_result: string | null;
  timestamp: string;
}

export interface CallSessionDetailOut extends CallSessionOut {
  logs: CallLogOut[];
}
