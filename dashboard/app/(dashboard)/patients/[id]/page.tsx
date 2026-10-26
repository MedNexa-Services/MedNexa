"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  getPatient,
  getPatientAppointments,
  type PatientOut,
  type AppointmentOut,
  type AppointmentStatus,
} from "@/lib/api";
import { PatientFormDialog } from "@/components/patients/PatientFormDialog";
import { BookAppointmentDialog } from "@/components/appointments/BookAppointmentDialog";
import { toast } from "sonner";
import {
  ArrowLeft,
  User,
  Phone,
  Mail,
  MapPin,
  Calendar,
  Clock,
  CheckCircle2,
  Ban,
  RefreshCw,
  ExternalLink,
  Edit2,
  CalendarPlus,
  Copy,
  Check,
  AlertCircle,
  FileText,
  Bot,
  Laptop,
  Footprints,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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

export default function PatientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = Array.isArray(params.id) ? params.id[0] : (params.id as string);

  const [patient, setPatient] = React.useState<PatientOut | null>(null);
  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [totalAppointments, setTotalAppointments] = React.useState(0);
  const [isLoading, setIsLoading] = React.useState(true);
  const [copiedPhone, setCopiedPhone] = React.useState(false);

  // Dialogs
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [bookDialogOpen, setBookDialogOpen] = React.useState(false);

  const fetchPatientData = React.useCallback(async () => {
    if (!patientId) return;
    setIsLoading(true);
    try {
      const [patientRes, appointmentsRes] = await Promise.all([
        getPatient(patientId),
        getPatientAppointments(patientId, { limit: 50 }),
      ]);
      setPatient(patientRes);
      setAppointments(appointmentsRes.items);
      setTotalAppointments(appointmentsRes.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load patient records";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [patientId]);

  React.useEffect(() => {
    fetchPatientData();
  }, [fetchPatientData]);

  const handleCopyPhone = () => {
    if (patient?.phone) {
      navigator.clipboard.writeText(patient.phone);
      setCopiedPhone(true);
      toast.success("Phone number copied to clipboard");
      setTimeout(() => setCopiedPhone(false), 2000);
    }
  };

  const getInitials = (nameStr: string) => {
    const parts = nameStr.trim().split(" ");
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return nameStr.slice(0, 2).toUpperCase();
  };

  const formatSlotTime = (timeStr: string) => {
    if (!timeStr) return "";
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr + "T00:00:00");
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  if (isLoading && !patient) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading patient profile...</p>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="space-y-4">
        <Link
          href="/patients"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Patient Directory</span>
        </Link>
        <Card className="p-8 text-center border-dashed border-border">
          <AlertCircle className="w-8 h-8 mx-auto text-amber-500 mb-2" />
          <h3 className="text-base font-semibold">Patient Not Found</h3>
          <Button size="sm" onClick={() => router.push("/patients")} className="mt-4">
            Return to Directory
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/patients"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Patient Directory</span>
        </Link>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setEditDialogOpen(true)}
            className="gap-1.5 cursor-pointer text-xs"
          >
            <Edit2 className="w-3.5 h-3.5" />
            <span>Edit Profile</span>
          </Button>

          <Button
            type="button"
            size="sm"
            onClick={() => setBookDialogOpen(true)}
            className="gap-1.5 cursor-pointer text-xs bg-primary text-primary-foreground"
          >
            <CalendarPlus className="w-3.5 h-3.5" />
            <span>Book Appointment</span>
          </Button>
        </div>
      </div>

      {/* Patient Profile Card */}
      <Card className="p-6 border-border bg-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/70">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary font-extrabold text-xl flex items-center justify-center border border-primary/20">
              {getInitials(patient.name)}
            </div>

            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                {patient.name}
                {patient.gender && (
                  <Badge variant="outline" className="text-xs font-normal capitalize">
                    {patient.gender.toLowerCase()}
                  </Badge>
                )}
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                <span>Patient ID:</span>
                <code className="px-1.5 py-0.5 rounded bg-muted font-mono text-[11px] text-foreground">
                  {patient.id}
                </code>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Badge
              variant="outline"
              className="text-xs px-3 py-1 font-semibold border-primary/30 text-primary bg-primary/5"
            >
              {totalAppointments} {totalAppointments === 1 ? "Appointment" : "Appointments"} Total
            </Badge>
          </div>
        </div>

        {/* Profile Attributes */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4 text-xs">
          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Primary Phone Number</span>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-foreground text-sm">{patient.phone}</span>
              <button
                type="button"
                onClick={handleCopyPhone}
                className="text-muted-foreground hover:text-foreground cursor-pointer p-1"
                title="Copy phone"
              >
                {copiedPhone ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Age</span>
            <span className="font-semibold text-foreground text-sm">
              {patient.age ? `${patient.age} years old` : "Not recorded"}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Email Address</span>
            <span className="font-medium text-foreground text-xs flex items-center gap-1">
              <Mail className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              {patient.email || "No email on file"}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Residential Address</span>
            <span className="font-medium text-foreground text-xs flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              {patient.address || "No address on file"}
            </span>
          </div>
        </div>
      </Card>

      {/* Appointment History Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Appointment &amp; Consultation History</h2>
          </div>

          <Button
            size="sm"
            onClick={() => setBookDialogOpen(true)}
            className="text-xs h-8 gap-1.5 cursor-pointer"
          >
            <CalendarPlus className="w-3.5 h-3.5" />
            <span>Book New Slot</span>
          </Button>
        </div>

        <Card className="border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">Token</TableHead>
                <TableHead>Date &amp; Time</TableHead>
                <TableHead>Doctor &amp; Department</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {appointments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <Calendar className="w-6 h-6 text-muted-foreground/60" />
                      <span className="text-xs font-semibold text-foreground">
                        No appointments found for this patient
                      </span>
                      <p className="text-[11px] text-muted-foreground">
                        Click &ldquo;Book New Slot&rdquo; above to schedule their first consultation.
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                appointments.map((apt) => {
                  const statusMeta = STATUS_CONFIG[apt.status] || STATUS_CONFIG.BOOKED;
                  const StatusIcon = statusMeta.icon;
                  const sourceMeta =
                    SOURCE_CONFIG[apt.booking_source as keyof typeof SOURCE_CONFIG] ||
                    SOURCE_CONFIG.DASHBOARD;
                  const SourceIcon = sourceMeta.icon;

                  return (
                    <TableRow key={apt.id} className="hover:bg-muted/40 transition-colors">
                      {/* Token # */}
                      <TableCell>
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-md text-xs font-extrabold bg-primary/10 text-primary border border-primary/20">
                          #{apt.token_number}
                        </span>
                      </TableCell>

                      {/* Date & Time */}
                      <TableCell>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1 font-semibold text-foreground text-xs">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                            <span>{formatSlotTime(apt.appointment_time)}</span>
                          </div>
                          <span className="text-[11px] text-muted-foreground block">
                            {formatDate(apt.appointment_date)}
                          </span>
                        </div>
                      </TableCell>

                      {/* Doctor */}
                      <TableCell>
                        <div className="space-y-0.5">
                          <span className="font-bold text-foreground text-xs block">
                            {apt.doctor_name}
                          </span>
                          <span className="text-[11px] text-muted-foreground block">
                            {apt.department}
                          </span>
                        </div>
                      </TableCell>

                      {/* Channel */}
                      <TableCell>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${sourceMeta.class}`}
                        >
                          <SourceIcon className="w-3 h-3" />
                          {sourceMeta.label}
                        </span>
                      </TableCell>

                      {/* Status */}
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`gap-1 text-[11px] font-medium ${statusMeta.badgeClass}`}
                        >
                          <StatusIcon className="w-3 h-3" />
                          {statusMeta.label}
                        </Badge>
                      </TableCell>

                      {/* Notes */}
                      <TableCell>
                        <span className="text-xs text-muted-foreground block max-w-[180px] truncate">
                          {apt.notes || "—"}
                        </span>
                      </TableCell>

                      {/* Actions */}
                      <TableCell className="text-right">
                        <Link
                          href={`/appointments/${apt.id}`}
                          className="inline-flex items-center justify-center h-8 px-2.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-muted text-foreground transition-colors cursor-pointer gap-1"
                        >
                          <span>Details</span>
                          <ExternalLink className="w-3 h-3 text-muted-foreground" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </Card>
      </div>

      {/* Edit Patient Dialog */}
      <PatientFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        patient={patient}
        onSuccess={fetchPatientData}
      />

      {/* Book Appointment Dialog */}
      <BookAppointmentDialog
        open={bookDialogOpen}
        onOpenChange={setBookDialogOpen}
        onSuccess={fetchPatientData}
      />
    </div>
  );
}
