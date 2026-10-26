"use client";

import * as React from "react";
import Link from "next/link";
import {
  CalendarCheck2,
  CalendarX2,
  Clock,
  PhoneCall,
  RefreshCw,
  Stethoscope,
  TrendingUp,
  User,
  Bot,
  Monitor,
  AlertCircle,
  ArrowRight,
  Calendar as CalendarIcon,
  Search,
} from "lucide-react";
import { listAppointments, listDoctors, type AppointmentOut, type DoctorOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

export default function DashboardOverviewPage() {
  const { hospital } = useHospital();

  // Selected date state (defaults to hospital-local today or 2026-10-25)
  const getTodayISO = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const [selectedDate, setSelectedDate] = React.useState<string>(getTodayISO);
  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [lastUpdated, setLastUpdated] = React.useState<Date>(new Date());

  // Fetch appointments and doctors for the selected date
  const loadData = React.useCallback(
    async (showToast = false) => {
      if (showToast) setIsRefreshing(true);
      try {
        const [apptsRes, docsRes] = await Promise.all([
          listAppointments({ date: selectedDate, limit: 50 }),
          listDoctors({ limit: 50, include_inactive: false }),
        ]);

        setAppointments(apptsRes.items || []);
        setDoctors(docsRes.items || []);
        setLastUpdated(new Date());

        if (showToast) {
          toast.success("Dashboard data refreshed");
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load dashboard data";
        toast.error(msg);
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [selectedDate]
  );

  // Initial fetch and on selectedDate change
  React.useEffect(() => {
    setIsLoading(true);
    loadData();
  }, [loadData]);

  // Polling: Auto-refresh every 30 seconds
  React.useEffect(() => {
    const interval = setInterval(() => {
      loadData(false);
    }, 30000);

    return () => clearInterval(interval);
  }, [loadData]);

  // Compute ISO Weekday for selected date (1 = Monday ... 7 = Sunday)
  const dateObj = new Date(selectedDate + "T00:00:00");
  const jsDay = dateObj.getDay(); // 0 is Sun, 1 is Mon
  const isoWeekday = jsDay === 0 ? 7 : jsDay;

  // Active doctors working on this specific weekday
  const activeDoctorsToday = doctors.filter((doc) =>
    doc.available_days?.includes(isoWeekday)
  );

  // Total daily slot capacity for today across working doctors
  const totalSlotsCapacity = activeDoctorsToday.reduce(
    (sum, doc) => sum + (doc.max_daily_appointments || 0),
    0
  );

  // Appointment counts
  const bookedCount = appointments.filter((a) => a.status === "BOOKED").length;
  const cancelledCount = appointments.filter((a) => a.status === "CANCELLED").length;
  const completedCount = appointments.filter((a) => a.status === "COMPLETED").length;
  const openSlots = Math.max(0, totalSlotsCapacity - bookedCount);

  // Filtered appointments by search term
  const filteredAppointments = appointments.filter(
    (a) =>
      a.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.doctor_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.patient_phone.includes(searchQuery)
  );

  // Format date for display
  const formattedSelectedDate = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(dateObj);

  const formatTime = (timeStr: string) => {
    const [h, m] = timeStr.split(":");
    const hour = parseInt(h, 10);
    const ampm = hour >= 12 ? "PM" : "AM";
    const formattedHour = hour % 12 || 12;
    return `${formattedHour}:${m} ${ampm}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "BOOKED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Booked
          </span>
        );
      case "CANCELLED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            Cancelled
          </span>
        );
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            Completed
          </span>
        );
      case "RESCHEDULED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Rescheduled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground">
            {status}
          </span>
        );
    }
  };

  const getSourceBadge = (source: string) => {
    switch (source) {
      case "AI_CALL":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-purple-600 dark:text-purple-400">
            <Bot className="w-3.5 h-3.5" />
            AI Phone
          </span>
        );
      case "DASHBOARD":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 dark:text-blue-400">
            <Monitor className="w-3.5 h-3.5" />
            Staff Portal
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
            <User className="w-3.5 h-3.5" />
            Walk-in
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Date Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">📊</span>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Today&apos;s Overview
            </h1>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            {formattedSelectedDate} • {hospital?.name ?? "MedNexa City Hospital"}
          </p>
        </div>

        {/* Date Filter & Manual Refresh */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center bg-card border border-border rounded-lg p-1 text-xs">
            <button
              type="button"
              onClick={() => setSelectedDate(getTodayISO())}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                selectedDate === getTodayISO()
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              Today
            </button>
            <button
              type="button"
              onClick={() => setSelectedDate("2026-10-26")}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                selectedDate === "2026-10-26"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              Oct 26 (Seeded)
            </button>
            <button
              type="button"
              onClick={() => setSelectedDate("2026-10-27")}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                selectedDate === "2026-10-27"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              Oct 27
            </button>
          </div>

          {/* Date Picker Input */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-card border border-border rounded-lg">
            <CalendarIcon className="w-3.5 h-3.5 text-muted-foreground" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
              className="bg-transparent text-xs text-foreground focus:outline-none cursor-pointer"
            />
          </div>

          {/* Refresh Button with 30s status */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadData(true)}
            disabled={isRefreshing}
            className="gap-1.5 text-xs h-9 cursor-pointer"
            title="Auto-refreshes every 30 seconds"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-muted-foreground ${
                isRefreshing ? "animate-spin text-blue-600" : ""
              }`}
            />
            <span className="hidden sm:inline">Sync</span>
          </Button>
        </div>
      </div>

      {/* 4 Stat Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {/* Total Capacity */}
        <Card className="p-4 md:p-5 border-border bg-card shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Total Capacity
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <CalendarCheck2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold text-foreground">
              {isLoading ? "..." : totalSlotsCapacity}
            </span>
            <span className="text-xs text-muted-foreground">
              across {activeDoctorsToday.length} doctor{activeDoctorsToday.length === 1 ? "" : "s"}
            </span>
          </div>
        </Card>

        {/* Booked Appointments */}
        <Card className="p-4 md:p-5 border-border bg-card shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
              Booked
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold text-foreground">
              {isLoading ? "..." : bookedCount}
            </span>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              {totalSlotsCapacity > 0
                ? `${Math.round((bookedCount / totalSlotsCapacity) * 100)}% filled`
                : `${bookedCount} active`}
            </span>
          </div>
        </Card>

        {/* Cancelled Slots */}
        <Card className="p-4 md:p-5 border-border bg-card shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider">
              Cancelled
            </span>
            <div className="w-8 h-8 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center">
              <CalendarX2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold text-foreground">
              {isLoading ? "..." : cancelledCount}
            </span>
            <span className="text-xs text-muted-foreground">re-released</span>
          </div>
        </Card>

        {/* Open Slots Available */}
        <Card className="p-4 md:p-5 border-border bg-card shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider">
              Open Slots
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold text-foreground">
              {isLoading ? "..." : openSlots}
            </span>
            <span className="text-xs text-muted-foreground">free to book</span>
          </div>
        </Card>
      </div>

      {/* Main Grid: Upcoming Appointments + Active Doctors */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Upcoming Appointments Table (2 Cols Wide) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-foreground">
                Upcoming Appointments
              </h2>
              <p className="text-xs text-muted-foreground">
                Showing scheduled patient consultations for {selectedDate}
              </p>
            </div>

            {/* Quick Search */}
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
              <Input
                placeholder="Search patient, phone, doctor..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-8 text-xs bg-card"
              />
            </div>
          </div>

          <Card className="border-border bg-card overflow-hidden shadow-xs">
            {isLoading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center justify-between gap-4 py-2 border-b border-border/50">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-muted animate-pulse" />
                      <div className="space-y-1">
                        <div className="w-28 h-3.5 bg-muted animate-pulse rounded" />
                        <div className="w-20 h-2.5 bg-muted/60 animate-pulse rounded" />
                      </div>
                    </div>
                    <div className="hidden sm:block space-y-1">
                      <div className="w-24 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-16 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                    <div className="w-16 h-5 rounded-full bg-muted animate-pulse" />
                    <div className="w-12 h-6 rounded bg-muted animate-pulse" />
                  </div>
                ))}
              </div>
            ) : filteredAppointments.length === 0 ? (
              /* Empty State */
              <div className="p-8 md:p-12 text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-muted text-muted-foreground flex items-center justify-center mx-auto">
                  <CalendarX2 className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-foreground">
                    No appointments found for {selectedDate}
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                    {searchQuery
                      ? "No records matched your search query. Try clearing the filter."
                      : selectedDate === getTodayISO()
                      ? "The hospital seed database scheduled consultations for tomorrow (Monday, Oct 26)."
                      : "There are no booked patient slots for this specific date."}
                  </p>
                </div>

                <div className="flex items-center justify-center gap-3 pt-2">
                  {selectedDate !== "2026-10-26" && (
                    <Button
                      size="sm"
                      onClick={() => setSelectedDate("2026-10-26")}
                      className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white cursor-pointer"
                    >
                      <span>View Oct 26 OPD (Seeded Data)</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  )}
                  <Link
                    href="/appointments"
                    className="px-3 py-1.5 text-xs rounded-lg border border-border bg-card hover:bg-muted font-medium text-foreground transition-colors"
                  >
                    Manage Appointments
                  </Link>
                </div>
              </div>
            ) : (
              /* Appointments Table */
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-b border-border bg-muted/40">
                      <TableHead className="w-16 text-xs font-semibold">Token</TableHead>
                      <TableHead className="text-xs font-semibold">Time</TableHead>
                      <TableHead className="text-xs font-semibold">Patient</TableHead>
                      <TableHead className="text-xs font-semibold">Doctor &amp; Dept</TableHead>
                      <TableHead className="text-xs font-semibold">Status</TableHead>
                      <TableHead className="text-xs font-semibold">Source</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAppointments.map((appt) => (
                      <TableRow
                        key={appt.id}
                        className="border-b border-border hover:bg-muted/30 transition-colors"
                      >
                        {/* Token # */}
                        <TableCell className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">
                          #{String(appt.token_number).padStart(2, "0")}
                        </TableCell>

                        {/* Appointment Time */}
                        <TableCell className="text-xs font-medium text-foreground">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                            <span>{formatTime(appt.appointment_time)}</span>
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {appt.slot_duration_minutes} min slot
                          </span>
                        </TableCell>

                        {/* Patient Name & Phone */}
                        <TableCell className="text-xs">
                          <div className="font-semibold text-foreground">
                            {appt.patient_name}
                          </div>
                          <div className="text-[11px] text-muted-foreground font-mono">
                            {appt.patient_phone}
                          </div>
                        </TableCell>

                        {/* Doctor & Department */}
                        <TableCell className="text-xs">
                          <div className="font-medium text-foreground">
                            {appt.doctor_name}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {appt.department}
                          </div>
                        </TableCell>

                        {/* Status Badge */}
                        <TableCell>{getStatusBadge(appt.status)}</TableCell>

                        {/* Booking Source */}
                        <TableCell>{getSourceBadge(appt.booking_source)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Active Doctors On Duty (1 Col Wide) */}
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-bold text-foreground">
              Doctors on Duty
            </h2>
            <p className="text-xs text-muted-foreground">
              {activeDoctorsToday.length} practitioner{activeDoctorsToday.length === 1 ? "" : "s"} scheduled today
            </p>
          </div>

          <Card className="p-4 border-border bg-card shadow-xs space-y-3">
            {activeDoctorsToday.length === 0 ? (
              <div className="py-8 text-center space-y-2">
                <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto" />
                <p className="text-xs text-muted-foreground">
                  No doctors scheduled on {dateObj.toLocaleDateString("en-US", { weekday: "long" })}s.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {activeDoctorsToday.map((doc) => {
                  const docAppointments = appointments.filter(
                    (a) => a.doctor_id === doc.id && a.status === "BOOKED"
                  );
                  const isFull = docAppointments.length >= doc.max_daily_appointments;

                  return (
                    <div key={doc.id} className="py-3 first:pt-0 last:pb-0 space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-600 flex items-center justify-center shrink-0">
                            <Stethoscope className="w-3.5 h-3.5" />
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-foreground">
                              {doc.name}
                            </h4>
                            <p className="text-[11px] text-muted-foreground">
                              {doc.speciality}
                            </p>
                          </div>
                        </div>

                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold shrink-0 ${
                            isFull
                              ? "bg-rose-500/10 text-rose-600 border border-rose-500/20"
                              : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                          }`}
                        >
                          {isFull ? "Full" : "Available"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                        <span>
                          {formatTime(doc.slot_start_time)} – {formatTime(doc.slot_end_time)}
                        </span>
                        <span className="font-medium text-foreground">
                          {docAppointments.length} / {doc.max_daily_appointments} slots
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="pt-2 border-t border-border">
              <Link
                href="/doctors"
                className="inline-flex items-center justify-center w-full py-2 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:bg-muted/50 rounded-lg transition-colors gap-1.5"
              >
                <span>View Full Medical Roster</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </Card>

          {/* AI Receptionist Quick Status Box */}
          <Card className="p-4 border-blue-500/20 bg-blue-500/5 shadow-xs space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <Bot className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span>AI Auto-Booking Active</span>
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold uppercase">
                Sync 30s
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              When callers book through the phone system, appointments will automatically appear here with assigned tokens.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
