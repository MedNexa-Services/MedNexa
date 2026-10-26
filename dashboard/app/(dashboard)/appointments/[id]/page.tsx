"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  getAppointment,
  type AppointmentOut,
  type AppointmentStatus,
} from "@/lib/api";
import { CancelAppointmentDialog } from "@/components/appointments/CancelAppointmentDialog";
import { RescheduleAppointmentDialog } from "@/components/appointments/RescheduleAppointmentDialog";
import { toast } from "sonner";
import {
  ArrowLeft,
  Calendar,
  Clock,
  User,
  Phone,
  Stethoscope,
  RefreshCw,
  Ban,
  CheckCircle2,
  FileText,
  Hash,
  ExternalLink,
  Bot,
  Laptop,
  Footprints,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const STATUS_CONFIG: Record<
  AppointmentStatus,
  { label: string; badgeClass: string; icon: React.ElementType }
> = {
  BOOKED: {
    label: "Booked",
    badgeClass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    icon: CheckCircle2,
  },
  CANCELLED: {
    label: "Cancelled",
    badgeClass: "bg-destructive/15 text-destructive border-destructive/30",
    icon: Ban,
  },
  COMPLETED: {
    label: "Completed",
    badgeClass: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30",
    icon: CheckCircle2,
  },
  RESCHEDULED: {
    label: "Rescheduled",
    badgeClass: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
    icon: RefreshCw,
  },
  NO_SHOW: {
    label: "No Show",
    badgeClass: "bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30",
    icon: Ban,
  },
};

const SOURCE_CONFIG = {
  AI_CALL: { label: "AI Call", icon: Bot, class: "text-purple-600 bg-purple-500/10 border-purple-500/20" },
  DASHBOARD: { label: "Dashboard", icon: Laptop, class: "text-blue-600 bg-blue-500/10 border-blue-500/20" },
  WALK_IN: { label: "Walk-in", icon: Footprints, class: "text-amber-600 bg-amber-500/10 border-amber-500/20" },
};

export default function AppointmentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const appointmentId = params?.id as string;

  const [appointment, setAppointment] = React.useState<AppointmentOut | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [cancelOpen, setCancelOpen] = React.useState(false);
  const [rescheduleOpen, setRescheduleOpen] = React.useState(false);

  const fetchAppointment = React.useCallback(async () => {
    if (!appointmentId) return;
    setIsLoading(true);
    try {
      const data = await getAppointment(appointmentId);
      setAppointment(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load appointment details";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [appointmentId]);

  React.useEffect(() => {
    fetchAppointment();
  }, [fetchAppointment]);

  const formatSlotTime = (timeStr: string) => {
    if (!timeStr) return "";
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  const formatDateTime = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "numeric",
        hour12: true,
      });
    } catch {
      return isoStr;
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading appointment details...</p>
      </div>
    );
  }

  if (!appointment) {
    return (
      <div className="space-y-4">
        <Link
          href="/appointments"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Appointments</span>
        </Link>
        <Card className="p-8 text-center border-dashed border-border">
          <AlertTriangle className="w-8 h-8 mx-auto text-amber-500 mb-2" />
          <h3 className="text-base font-semibold">Appointment Not Found</h3>
          <p className="text-xs text-muted-foreground mt-1 mb-4">
            The requested appointment record does not exist or has been removed.
          </p>
          <Button size="sm" onClick={() => router.push("/appointments")}>
            Return to Appointments
          </Button>
        </Card>
      </div>
    );
  }

  const statusMeta = STATUS_CONFIG[appointment.status] || STATUS_CONFIG.BOOKED;
  const StatusIcon = statusMeta.icon;
  const sourceMeta =
    SOURCE_CONFIG[appointment.booking_source as keyof typeof SOURCE_CONFIG] ||
    SOURCE_CONFIG.DASHBOARD;
  const SourceIcon = sourceMeta.icon;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Breadcrumb back navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/appointments"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Appointments</span>
        </Link>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={`gap-1 text-xs font-semibold px-2.5 py-1 ${statusMeta.badgeClass}`}
          >
            <StatusIcon className="w-3.5 h-3.5" />
            {statusMeta.label}
          </Badge>
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${sourceMeta.class}`}
          >
            <SourceIcon className="w-3.5 h-3.5" />
            {sourceMeta.label}
          </span>
        </div>
      </div>

      {/* Main Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 bg-card border border-border rounded-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary flex flex-col items-center justify-center font-bold">
            <span className="text-[10px] uppercase tracking-wider font-semibold opacity-75">Token</span>
            <span className="text-2xl leading-none">#{appointment.token_number}</span>
          </div>

          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              {appointment.patient_name}
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
              <span>Appointment ID:</span>
              <code className="px-1.5 py-0.5 rounded bg-muted font-mono text-[11px] text-foreground">
                {appointment.id}
              </code>
            </p>
          </div>
        </div>

        {appointment.status === "BOOKED" && (
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRescheduleOpen(true)}
              className="gap-1.5 cursor-pointer text-amber-600 dark:text-amber-400 hover:bg-amber-500/10"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reschedule Slot</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCancelOpen(true)}
              className="gap-1.5 cursor-pointer text-destructive hover:bg-destructive/10"
            >
              <Ban className="w-4 h-4" />
              <span>Cancel Appointment</span>
            </Button>
          </div>
        )}
      </div>

      {/* Grid of detail sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Section 1: Patient Information */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border">
            <div className="flex items-center gap-2 font-semibold text-sm text-foreground">
              <User className="w-4 h-4 text-primary" />
              <span>Patient Profile</span>
            </div>
            <Link
              href={`/patients/${appointment.patient_id}`}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              <span>View History</span>
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Full Name:</span>
              <span className="font-semibold text-foreground">{appointment.patient_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Phone Number:</span>
              <span className="font-semibold text-foreground flex items-center gap-1">
                <Phone className="w-3 h-3 text-muted-foreground" />
                {appointment.patient_phone}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Patient Record ID:</span>
              <code className="text-[11px] font-mono text-muted-foreground">
                {appointment.patient_id}
              </code>
            </div>
          </div>
        </Card>

        {/* Section 2: Consulting Doctor & Slot */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border">
            <div className="flex items-center gap-2 font-semibold text-sm text-foreground">
              <Stethoscope className="w-4 h-4 text-primary" />
              <span>Doctor &amp; Slot Schedule</span>
            </div>
            <Link
              href={`/doctors/${appointment.doctor_id}`}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              <span>Doctor Profile</span>
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Doctor Name:</span>
              <span className="font-semibold text-foreground">{appointment.doctor_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Department:</span>
              <Badge variant="outline" className="text-[11px]">
                {appointment.department}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Scheduled Date:</span>
              <span className="font-semibold text-foreground flex items-center gap-1">
                <Calendar className="w-3 h-3 text-muted-foreground" />
                {appointment.appointment_date}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Time Slot:</span>
              <span className="font-semibold text-primary flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                {formatSlotTime(appointment.appointment_time)} ({appointment.slot_duration_minutes} min)
              </span>
            </div>
          </div>
        </Card>

        {/* Section 3: Visit Notes & Clinical Purpose */}
        <Card className="p-6 space-y-3 md:col-span-2">
          <div className="flex items-center gap-2 font-semibold text-sm text-foreground pb-2 border-b border-border">
            <FileText className="w-4 h-4 text-primary" />
            <span>Clinical Purpose &amp; Consultation Notes</span>
          </div>

          <div className="text-xs">
            {appointment.notes ? (
              <p className="text-foreground leading-relaxed p-3 bg-muted/30 rounded-lg border border-border">
                {appointment.notes}
              </p>
            ) : (
              <p className="text-muted-foreground italic">
                No specific visit notes were provided during the booking.
              </p>
            )}
          </div>
        </Card>

        {/* Section 4: Audit & Lifecycle Log */}
        <Card className="p-6 space-y-3 md:col-span-2 bg-muted/20">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Audit Trail &amp; Lifecycle Events
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-2.5 rounded-lg bg-card border border-border">
              <span className="text-muted-foreground block text-[11px]">Created At</span>
              <span className="font-medium text-foreground">{formatDateTime(appointment.created_at)}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-card border border-border">
              <span className="text-muted-foreground block text-[11px]">Booking Channel</span>
              <span className="font-medium text-foreground">{sourceMeta.label}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-card border border-border">
              <span className="text-muted-foreground block text-[11px]">Queue Token</span>
              <span className="font-extrabold text-primary">#{appointment.token_number}</span>
            </div>
          </div>

          {appointment.cancellation_reason && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive space-y-1">
              <span className="font-semibold block">Cancellation Reason:</span>
              <p>{appointment.cancellation_reason}</p>
              {appointment.cancelled_at && (
                <span className="text-[11px] opacity-80 block">
                  Cancelled at {formatDateTime(appointment.cancelled_at)}
                </span>
              )}
            </div>
          )}

          {appointment.rescheduled_from_id && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-400">
              <span className="font-semibold block">Rescheduled from prior booking:</span>
              <code className="text-[11px] font-mono">{appointment.rescheduled_from_id}</code>
            </div>
          )}
        </Card>
      </div>

      {/* Cancel Confirmation Dialog */}
      <CancelAppointmentDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        appointment={appointment}
        onSuccess={fetchAppointment}
      />

      {/* Reschedule Dialog */}
      <RescheduleAppointmentDialog
        open={rescheduleOpen}
        onOpenChange={setRescheduleOpen}
        appointment={appointment}
        onSuccess={fetchAppointment}
      />
    </div>
  );
}
