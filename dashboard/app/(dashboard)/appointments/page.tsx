"use client";

import * as React from "react";
import Link from "next/link";
import {
  listAppointments,
  listDoctors,
  type AppointmentOut,
  type DoctorOut,
  type AppointmentStatus,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { addDays, todayIn } from "@/lib/dates";
import { BookAppointmentDialog } from "@/components/appointments/BookAppointmentDialog";
import { CancelAppointmentDialog } from "@/components/appointments/CancelAppointmentDialog";
import { RescheduleAppointmentDialog } from "@/components/appointments/RescheduleAppointmentDialog";
import { toast } from "sonner";
import {
  Calendar,
  Clock,
  User,
  Filter,
  Plus,
  RefreshCw,
  Search,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Bot,
  Laptop,
  Footprints,
  CalendarCheck2,
  Ban,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

export default function AppointmentsPage() {
  const { hospitalId, hospital } = useHospital();

  // Filters
  // null = today (in the hospital's timezone), "" = all dates, otherwise a picked date
  const [pickedDate, setPickedDate] = React.useState<string | null>(null);
  const today = todayIn(hospital?.timezone);
  const tomorrow = addDays(today, 1);
  const selectedDate = pickedDate ?? today;
  const setSelectedDate = setPickedDate;
  const [selectedDoctorId, setSelectedDoctorId] = React.useState<string>("");
  const [selectedStatus, setSelectedStatus] = React.useState<string>("");
  const [searchQuery, setSearchQuery] = React.useState<string>("");

  // Pagination
  const [pageIndex, setPageIndex] = React.useState(0);
  const pageSize = 15;

  // Data states
  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [totalCount, setTotalCount] = React.useState(0);
  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);

  // Dialog states
  const [bookDialogOpen, setBookDialogOpen] = React.useState(false);
  const [cancelTarget, setCancelTarget] = React.useState<AppointmentOut | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = React.useState<AppointmentOut | null>(null);

  // Load doctors for dropdown
  React.useEffect(() => {
    if (!hospitalId) return;
    async function fetchDoctors() {
      try {
        const res = await listDoctors({ hospital_id: hospitalId, limit: 100 });
        setDoctors(res.items);
      } catch (err: unknown) {
        console.error("Failed to load doctors:", err);
      }
    }
    fetchDoctors();
  }, [hospitalId]);

  // Fetch appointments based on filters & pagination
  const fetchAppointments = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Parameters<typeof listAppointments>[0] = {
        limit: pageSize,
        offset: pageIndex * pageSize,
      };

      if (hospitalId) params.hospital_id = hospitalId;
      if (selectedDate) params.date = selectedDate;
      if (selectedDoctorId) params.doctor_id = selectedDoctorId;
      if (selectedStatus) params.status = selectedStatus as AppointmentStatus;

      const res = await listAppointments(params);
      setAppointments(res.items);
      setTotalCount(res.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load appointments";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, selectedDate, selectedDoctorId, selectedStatus, pageIndex]);

  React.useEffect(() => {
    fetchAppointments();
  }, [fetchAppointments]);

  // Reset page when filters change
  const handleFilterChange = (setter: (val: string) => void, val: string) => {
    setter(val);
    setPageIndex(0);
  };

  const handleClearFilters = () => {
    setSelectedDate("");
    setSelectedDoctorId("");
    setSelectedStatus("");
    setSearchQuery("");
    setPageIndex(0);
  };

  // Client-side text search (on patient name or phone)
  const filteredAppointments = React.useMemo(() => {
    if (!searchQuery.trim()) return appointments;
    const q = searchQuery.toLowerCase();
    return appointments.filter(
      (a) =>
        a.patient_name.toLowerCase().includes(q) ||
        a.patient_phone.toLowerCase().includes(q) ||
        a.doctor_name.toLowerCase().includes(q) ||
        a.token_number.toString().includes(q)
    );
  }, [appointments, searchQuery]);

  // Stats derived from loaded data
  const bookedCount = filteredAppointments.filter((a) => a.status === "BOOKED").length;
  const cancelledCount = filteredAppointments.filter((a) => a.status === "CANCELLED").length;
  const rescheduledCount = filteredAppointments.filter((a) => a.status === "RESCHEDULED").length;

  const formatSlotTime = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  const formatDateLabel = (dateStr: string) => {
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

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <CalendarCheck2 className="w-6 h-6 text-primary" />
            Appointments Management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time daily schedule, token queues, and staff booking, cancellation, and rescheduling.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchAppointments()}
            className="gap-1.5 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>

          <Button
            size="sm"
            onClick={() => setBookDialogOpen(true)}
            className="gap-2 cursor-pointer shadow-sm bg-primary text-primary-foreground"
          >
            <Plus className="w-4 h-4" />
            <span>Book Appointment</span>
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-4 space-y-3 bg-card border-border">
        {/* Quick Date Presets */}
        <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-border/60">
          <span className="text-xs font-semibold text-muted-foreground mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3" />
            Date Filter:
          </span>
          <button
            type="button"
            onClick={() => handleFilterChange(setSelectedDate, "")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              selectedDate === ""
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            All Dates
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange(setSelectedDate, today)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              selectedDate === today
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange(setSelectedDate, tomorrow)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              selectedDate === tomorrow
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            Tomorrow
          </button>

          <div className="ml-auto flex items-center gap-2">
            <Label htmlFor="custom-date-filter" className="text-xs text-muted-foreground hidden sm:inline">
              Custom:
            </Label>
            <Input
              id="custom-date-filter"
              type="date"
              value={selectedDate}
              onChange={(e) => handleFilterChange(setSelectedDate, e.target.value)}
              className="h-8 w-36 text-xs"
            />
          </div>
        </div>

        {/* Dropdowns & Search */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {/* Doctor Filter */}
          <div className="space-y-1">
            <Label htmlFor="filter-doctor" className="text-[11px] font-semibold text-muted-foreground">
              Filter by Doctor
            </Label>
            <select
              id="filter-doctor"
              value={selectedDoctorId}
              onChange={(e) => handleFilterChange(setSelectedDoctorId, e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">All Doctors ({doctors.length})</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.department})
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="space-y-1">
            <Label htmlFor="filter-status" className="text-[11px] font-semibold text-muted-foreground">
              Filter by Status
            </Label>
            <select
              id="filter-status"
              value={selectedStatus}
              onChange={(e) => handleFilterChange(setSelectedStatus, e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">All Statuses</option>
              <option value="BOOKED">Booked</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="RESCHEDULED">Rescheduled</option>
              <option value="NO_SHOW">No Show</option>
            </select>
          </div>

          {/* Text Search */}
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="filter-search" className="text-[11px] font-semibold text-muted-foreground">
              Search Patient or Token
            </Label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="filter-search"
                placeholder="Search by patient name, phone, or token #..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-9 text-xs"
              />
              {(selectedDate || selectedDoctorId || selectedStatus || searchQuery) && (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground cursor-pointer flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Mini Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-card border border-border rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-muted-foreground block font-medium">Total In View</span>
            <span className="text-xl font-bold text-foreground">{totalCount}</span>
          </div>
          <Calendar className="w-5 h-5 text-muted-foreground opacity-60" />
        </div>

        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-emerald-700 dark:text-emerald-400 block font-medium">Booked</span>
            <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{bookedCount}</span>
          </div>
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
        </div>

        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-destructive block font-medium">Cancelled</span>
            <span className="text-xl font-bold text-destructive">{cancelledCount}</span>
          </div>
          <Ban className="w-5 h-5 text-destructive" />
        </div>

        <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-amber-700 dark:text-amber-400 block font-medium">Rescheduled</span>
            <span className="text-xl font-bold text-amber-700 dark:text-amber-400">{rescheduledCount}</span>
          </div>
          <RefreshCw className="w-5 h-5 text-amber-600" />
        </div>
      </div>

      {/* Appointments Table */}
      <Card className="border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">Token</TableHead>
              <TableHead>Date &amp; Time</TableHead>
              <TableHead>Doctor &amp; Department</TableHead>
              <TableHead>Patient Details</TableHead>
              <TableHead>Booking Source</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i}>
                  <TableCell><div className="w-8 h-6 rounded bg-muted animate-pulse" /></TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="w-16 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-20 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="w-28 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-16 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="w-24 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-20 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                  </TableCell>
                  <TableCell><div className="w-16 h-5 rounded-full bg-muted animate-pulse" /></TableCell>
                  <TableCell><div className="w-16 h-5 rounded-full bg-muted animate-pulse" /></TableCell>
                  <TableCell className="text-right"><div className="w-20 h-7 rounded bg-muted animate-pulse ml-auto" /></TableCell>
                </TableRow>
              ))
            ) : filteredAppointments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-36 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                    <CalendarCheck2 className="w-8 h-8 text-muted-foreground/50" />
                    <span className="text-sm font-semibold text-foreground">No appointments found</span>
                    <p className="text-xs text-muted-foreground">
                      No bookings match your current date, doctor, or status filters.
                    </p>
                    <div className="flex gap-2 mt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleFilterChange(setSelectedDate, "")}
                        className="text-xs cursor-pointer"
                      >
                        Show All Dates
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => setBookDialogOpen(true)}
                        className="text-xs cursor-pointer"
                      >
                        Book First Slot
                      </Button>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredAppointments.map((apt) => {
                const statusMeta = STATUS_CONFIG[apt.status] || STATUS_CONFIG.BOOKED;
                const StatusIcon = statusMeta.icon;
                const sourceMeta =
                  SOURCE_CONFIG[apt.booking_source as keyof typeof SOURCE_CONFIG] ||
                  SOURCE_CONFIG.DASHBOARD;
                const SourceIcon = sourceMeta.icon;

                return (
                  <TableRow key={apt.id} className="hover:bg-muted/40 transition-colors">
                    {/* Token Number */}
                    <TableCell>
                      <span className="inline-flex items-center justify-center px-2 py-1 rounded-md text-xs font-extrabold bg-primary/10 text-primary border border-primary/20">
                        #{apt.token_number}
                      </span>
                    </TableCell>

                    {/* Date & Time */}
                    <TableCell>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5 font-medium text-foreground text-xs">
                          <Clock className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span>{formatSlotTime(apt.appointment_time)}</span>
                        </div>
                        <span className="text-[11px] text-muted-foreground block">
                          {formatDateLabel(apt.appointment_date)}
                        </span>
                      </div>
                    </TableCell>

                    {/* Doctor */}
                    <TableCell>
                      <div className="space-y-0.5">
                        <span className="font-semibold text-foreground text-xs block">
                          {apt.doctor_name}
                        </span>
                        <span className="text-[11px] text-muted-foreground block">
                          {apt.department}
                        </span>
                      </div>
                    </TableCell>

                    {/* Patient */}
                    <TableCell>
                      <div className="space-y-0.5">
                        <span className="font-semibold text-foreground text-xs flex items-center gap-1">
                          <User className="w-3 h-3 text-muted-foreground" />
                          {apt.patient_name}
                        </span>
                        <span className="text-[11px] text-muted-foreground block">
                          {apt.patient_phone}
                        </span>
                      </div>
                    </TableCell>

                    {/* Source */}
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

                    {/* Actions */}
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {apt.status === "BOOKED" && (
                          <>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => setRescheduleTarget(apt)}
                              className="h-8 px-2 text-xs text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 cursor-pointer"
                              title="Reschedule slot"
                            >
                              <RefreshCw className="w-3.5 h-3.5 mr-1" />
                              <span className="hidden sm:inline">Reschedule</span>
                            </Button>

                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => setCancelTarget(apt)}
                              className="h-8 px-2 text-xs text-destructive hover:bg-destructive/10 cursor-pointer"
                              title="Cancel appointment"
                            >
                              <Ban className="w-3.5 h-3.5 mr-1" />
                              <span className="hidden sm:inline">Cancel</span>
                            </Button>
                          </>
                        )}

                        <Link
                          href={`/appointments/${apt.id}`}
                          className="inline-flex items-center justify-center h-8 px-2.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-muted text-foreground transition-colors cursor-pointer"
                        >
                          <span>Details</span>
                          <ExternalLink className="w-3 h-3 ml-1 text-muted-foreground" />
                        </Link>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground bg-muted/20">
          <div>
            Showing{" "}
            <span className="font-semibold text-foreground">
              {totalCount === 0 ? 0 : pageIndex * pageSize + 1}
            </span>{" "}
            to{" "}
            <span className="font-semibold text-foreground">
              {Math.min((pageIndex + 1) * pageSize, totalCount)}
            </span>{" "}
            of <span className="font-semibold text-foreground">{totalCount}</span> appointments
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={pageIndex === 0}
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              className="h-8 gap-1 cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </Button>
            <span className="text-xs font-medium px-2">Page {pageIndex + 1}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={(pageIndex + 1) * pageSize >= totalCount}
              onClick={() => setPageIndex((p) => p + 1)}
              className="h-8 gap-1 cursor-pointer"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Booking Wizard Dialog */}
      <BookAppointmentDialog
        open={bookDialogOpen}
        onOpenChange={setBookDialogOpen}
        defaultDate={selectedDate || undefined}
        defaultDoctorId={selectedDoctorId || undefined}
        onSuccess={fetchAppointments}
      />

      {/* Cancel Confirmation Dialog */}
      <CancelAppointmentDialog
        open={!!cancelTarget}
        onOpenChange={(open) => !open && setCancelTarget(null)}
        appointment={cancelTarget}
        onSuccess={fetchAppointments}
      />

      {/* Reschedule Dialog */}
      <RescheduleAppointmentDialog
        open={!!rescheduleTarget}
        onOpenChange={(open) => !open && setRescheduleTarget(null)}
        appointment={rescheduleTarget}
        onSuccess={fetchAppointments}
      />
    </div>
  );
}
