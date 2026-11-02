import type { AppointmentStatus, BookingSource, CallOutcome } from "@/lib/api";
import { cn } from "@/lib/utils";

const APPOINTMENT: Record<AppointmentStatus, { label: string; tone: string }> = {
  BOOKED: { label: "Booked", tone: "bg-status-booked" },
  COMPLETED: { label: "Completed", tone: "bg-status-done" },
  CANCELLED: { label: "Cancelled", tone: "bg-status-cancelled" },
  RESCHEDULED: { label: "Rescheduled", tone: "bg-status-moved" },
  NO_SHOW: { label: "No-show", tone: "bg-status-moved" },
};

export const APPOINTMENT_STATUS_LABELS: Record<AppointmentStatus, string> = Object.fromEntries(
  Object.entries(APPOINTMENT).map(([status, { label }]) => [status, label])
) as Record<AppointmentStatus, string>;

function Dot({ className }: { className: string }) {
  return <span aria-hidden className={cn("inline-block size-1.5 shrink-0 rounded-full", className)} />;
}

export function AppointmentStatusLabel({ status }: { status: AppointmentStatus }) {
  const { label, tone } = APPOINTMENT[status] ?? { label: status, tone: "bg-status-done" };
  return (
    <span className="inline-flex items-center gap-1.5 text-sm whitespace-nowrap text-foreground">
      <Dot className={tone} />
      {label}
    </span>
  );
}

export const BOOKING_SOURCE_LABELS: Record<BookingSource, string> = {
  AI_CALL: "Phone (AI)",
  DASHBOARD: "Front desk",
  WALK_IN: "Walk-in",
};

export function BookingSourceLabel({ source }: { source: BookingSource }) {
  return <span className="text-sm text-muted-foreground">{BOOKING_SOURCE_LABELS[source] ?? source}</span>;
}

export const CALL_OUTCOME_LABELS: Record<CallOutcome, string> = {
  BOOKED: "Booked",
  CANCELLED: "Cancelled",
  RESCHEDULED: "Rescheduled",
  INFO_PROVIDED: "Answered a question",
  ESCALATED: "Passed to staff",
  ABANDONED: "Caller hung up",
  OTHER: "Other",
};

export function CallOutcomeLabel({ outcome, ended }: { outcome: CallOutcome | null; ended: boolean }) {
  if (!ended) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
        <Dot className="bg-status-booked" />
        On the line
      </span>
    );
  }
  const tone =
    outcome === "ESCALATED"
      ? "bg-status-moved"
      : outcome === "ABANDONED"
        ? "bg-status-cancelled"
        : outcome && outcome !== "OTHER" && outcome !== "INFO_PROVIDED"
          ? "bg-status-booked"
          : "bg-status-done";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm whitespace-nowrap text-foreground">
      <Dot className={tone} />
      {outcome ? CALL_OUTCOME_LABELS[outcome] : "No outcome"}
    </span>
  );
}
