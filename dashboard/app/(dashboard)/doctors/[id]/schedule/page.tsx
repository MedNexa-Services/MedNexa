"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  getDoctor,
  updateDoctor,
  listScheduleOverrides,
  deleteScheduleOverride,
  type DoctorDetailOut,
  type ScheduleOverrideOut,
} from "@/lib/api";
import { ScheduleOverrideDialog } from "@/components/doctors/ScheduleOverrideDialog";
import { toast } from "sonner";
import {
  ArrowLeft,
  Calendar,
  Clock,
  User,
  Plus,
  RefreshCw,
  Edit2,
  Trash2,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Ban,
  CheckCircle2,
  Sparkles,
  CalendarDays,
  Sliders,
  Check,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const WEEKDAYS = [
  { day: 1, label: "Mon", full: "Monday" },
  { day: 2, label: "Tue", full: "Tuesday" },
  { day: 3, label: "Wed", full: "Wednesday" },
  { day: 4, label: "Thu", full: "Thursday" },
  { day: 5, label: "Fri", full: "Friday" },
  { day: 6, label: "Sat", full: "Saturday" },
  { day: 7, label: "Sun", full: "Sunday" },
];

export default function DoctorSchedulePage() {
  const params = useParams();
  const router = useRouter();
  const doctorId = Array.isArray(params.id) ? params.id[0] : (params.id as string);

  const [doctor, setDoctor] = React.useState<DoctorDetailOut | null>(null);
  const [overrides, setOverrides] = React.useState<ScheduleOverrideOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);

  // Month navigation (defaults to Oct 2026 for seeded data)
  const [currentYear, setCurrentYear] = React.useState(2026);
  const [currentMonth, setCurrentMonth] = React.useState(9); // 0-indexed: 9 = October

  // Dialogs
  const [overrideDialogOpen, setOverrideDialogOpen] = React.useState(false);
  const [selectedDate, setSelectedDate] = React.useState<string | undefined>(undefined);
  const [activeOverride, setActiveOverride] = React.useState<ScheduleOverrideOut | null>(null);

  // Weekly Template Edit Modal
  const [templateModalOpen, setTemplateModalOpen] = React.useState(false);
  const [templateDays, setTemplateDays] = React.useState<number[]>([]);
  const [templateStart, setTemplateStart] = React.useState("09:00");
  const [templateEnd, setTemplateEnd] = React.useState("13:00");
  const [templateDuration, setTemplateDuration] = React.useState(15);
  const [templateMaxDaily, setTemplateMaxDaily] = React.useState(16);
  const [isSavingTemplate, setIsSavingTemplate] = React.useState(false);

  // Load doctor details
  const fetchDoctor = React.useCallback(async () => {
    if (!doctorId) return;
    try {
      const data = await getDoctor(doctorId);
      setDoctor(data);
      setTemplateDays(data.available_days || []);
      setTemplateStart(data.slot_start_time ? data.slot_start_time.slice(0, 5) : "09:00");
      setTemplateEnd(data.slot_end_time ? data.slot_end_time.slice(0, 5) : "13:00");
      setTemplateDuration(data.slot_duration_minutes || 15);
      setTemplateMaxDaily(data.max_daily_appointments || 16);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load doctor profile";
      toast.error(msg);
    }
  }, [doctorId]);

  // Load overrides for viewing month
  const fetchOverrides = React.useCallback(async () => {
    if (!doctorId) return;
    setIsLoading(true);
    try {
      // First and last day of month
      const startOfMonth = new Date(Date.UTC(currentYear, currentMonth, 1));
      const endOfMonth = new Date(Date.UTC(currentYear, currentMonth + 1, 0));

      const fromStr = startOfMonth.toISOString().split("T")[0];
      const toStr = endOfMonth.toISOString().split("T")[0];

      const data = await listScheduleOverrides(doctorId, { from: fromStr, to: toStr });
      setOverrides(data);
    } catch (err: unknown) {
      console.error("Failed to load schedule overrides:", err);
    } finally {
      setIsLoading(false);
    }
  }, [doctorId, currentYear, currentMonth]);

  React.useEffect(() => {
    fetchDoctor();
  }, [fetchDoctor]);

  React.useEffect(() => {
    fetchOverrides();
  }, [fetchOverrides]);

  const handlePrevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  const handleOpenAddOverride = (dateStr?: string) => {
    const existing = dateStr ? overrides.find((o) => o.date === dateStr) : null;
    setSelectedDate(dateStr);
    setActiveOverride(existing || null);
    setOverrideDialogOpen(true);
  };

  const handleDeleteOverride = async (dateStr: string) => {
    try {
      await deleteScheduleOverride(doctorId, dateStr);
      toast.success(`Removed override for ${dateStr}`);
      fetchOverrides();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete override";
      toast.error(msg);
    }
  };

  const handleSaveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (templateDays.length === 0) {
      toast.error("Please select at least one working day.");
      return;
    }
    if (templateEnd <= templateStart) {
      toast.error("Shift end time must be after start time.");
      return;
    }

    setIsSavingTemplate(true);
    try {
      await updateDoctor(doctorId, {
        available_days: templateDays,
        slot_start_time: `${templateStart}:00`,
        slot_end_time: `${templateEnd}:00`,
        slot_duration_minutes: templateDuration,
        max_daily_appointments: templateMaxDaily,
      });

      toast.success("Doctor's weekly schedule template updated!");
      await fetchDoctor();
      setTemplateModalOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update schedule template";
      toast.error(msg);
    } finally {
      setIsSavingTemplate(false);
    }
  };

  const formatSlotTime = (timeStr?: string | null) => {
    if (!timeStr) return "";
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  // Calendar matrix calculation
  const calendarDays = React.useMemo(() => {
    const firstDayOfMonth = new Date(currentYear, currentMonth, 1);
    const lastDayOfMonth = new Date(currentYear, currentMonth + 1, 0);

    const daysInMonth = lastDayOfMonth.getDate();
    // getDay() gives 0 for Sunday, 1 for Monday, etc.
    const startDayOfWeek = firstDayOfMonth.getDay();

    const cells: {
      dateStr: string;
      dayNumber: number;
      isCurrentMonth: boolean;
      weekdayIso: number; // 1=Mon, ..., 7=Sun
    }[] = [];

    // Prev month filler
    const prevMonthLastDate = new Date(currentYear, currentMonth, 0).getDate();
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const d = prevMonthLastDate - i;
      const prevDate = new Date(currentYear, currentMonth - 1, d);
      const isoWeekday = prevDate.getDay() === 0 ? 7 : prevDate.getDay();
      const monthStr = String(prevDate.getMonth() + 1).padStart(2, "0");
      const dateStr = `${prevDate.getFullYear()}-${monthStr}-${String(d).padStart(2, "0")}`;
      cells.push({
        dateStr,
        dayNumber: d,
        isCurrentMonth: false,
        weekdayIso: isoWeekday,
      });
    }

    // Current month days
    for (let d = 1; d <= daysInMonth; d++) {
      const currDate = new Date(currentYear, currentMonth, d);
      const isoWeekday = currDate.getDay() === 0 ? 7 : currDate.getDay();
      const monthStr = String(currentMonth + 1).padStart(2, "0");
      const dateStr = `${currentYear}-${monthStr}-${String(d).padStart(2, "0")}`;
      cells.push({
        dateStr,
        dayNumber: d,
        isCurrentMonth: true,
        weekdayIso: isoWeekday,
      });
    }

    // Next month filler to round to complete weeks (multiple of 7)
    const remaining = (7 - (cells.length % 7)) % 7;
    for (let d = 1; d <= remaining; d++) {
      const nextDate = new Date(currentYear, currentMonth + 1, d);
      const isoWeekday = nextDate.getDay() === 0 ? 7 : nextDate.getDay();
      const monthStr = String(nextDate.getMonth() + 1).padStart(2, "0");
      const dateStr = `${nextDate.getFullYear()}-${monthStr}-${String(d).padStart(2, "0")}`;
      cells.push({
        dateStr,
        dayNumber: d,
        isCurrentMonth: false,
        weekdayIso: isoWeekday,
      });
    }

    return cells;
  }, [currentYear, currentMonth]);

  const monthLabel = new Date(currentYear, currentMonth, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  if (!doctor && isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading doctor schedule...</p>
      </div>
    );
  }

  if (!doctor) {
    return (
      <div className="space-y-4">
        <Link
          href="/doctors"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Doctors</span>
        </Link>
        <Card className="p-8 text-center border-dashed border-border">
          <AlertCircle className="w-8 h-8 mx-auto text-amber-500 mb-2" />
          <h3 className="text-base font-semibold">Doctor Not Found</h3>
          <Button size="sm" onClick={() => router.push("/doctors")} className="mt-4">
            Return to Doctors List
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href="/doctors"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Doctors
            </Link>
            <span className="text-xs text-muted-foreground">/</span>
            <Link
              href={`/doctors/${doctor.id}`}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {doctor.name}
            </Link>
            <span className="text-xs text-muted-foreground">/</span>
            <span className="text-xs font-semibold text-foreground">Schedule &amp; Overrides</span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <CalendarDays className="w-6 h-6 text-primary" />
            {doctor.name} — Schedule &amp; Overrides
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {doctor.speciality} • {doctor.department}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTemplateModalOpen(true)}
            className="gap-1.5 cursor-pointer text-xs"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Edit Weekly Template</span>
          </Button>

          <Button
            size="sm"
            onClick={() => handleOpenAddOverride()}
            className="gap-1.5 cursor-pointer text-xs bg-primary text-primary-foreground"
          >
            <Plus className="w-4 h-4" />
            <span>Add Date Override</span>
          </Button>
        </div>
      </div>

      {/* Section 1: Weekly Template Panel */}
      <Card className="p-5 border-border bg-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">Standard Weekly Template</h3>
              <p className="text-xs text-muted-foreground">
                Base recurring shift hours automatically applied unless a date override exists.
              </p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setTemplateModalOpen(true)}
            className="text-xs text-primary hover:bg-primary/10 h-8 px-2.5 self-start sm:self-auto"
          >
            <Edit2 className="w-3.5 h-3.5 mr-1" />
            Modify Template
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          {/* Active Days */}
          <div className="space-y-1.5 md:col-span-2">
            <span className="text-muted-foreground block font-medium">Weekly Available Days</span>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((wd) => {
                const isActive = doctor.available_days.includes(wd.day);
                return (
                  <span
                    key={wd.day}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold ${
                      isActive
                        ? "bg-primary/15 text-primary border border-primary/30"
                        : "bg-muted text-muted-foreground line-through opacity-60"
                    }`}
                  >
                    {wd.label}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Normal Hours */}
          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Shift Timings</span>
            <span className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-primary" />
              {formatSlotTime(doctor.slot_start_time)} – {formatSlotTime(doctor.slot_end_time)}
            </span>
          </div>

          {/* Slot Duration & Max Daily */}
          <div className="space-y-1">
            <span className="text-muted-foreground block font-medium">Slot Configuration</span>
            <div className="space-y-0.5">
              <span className="font-semibold text-foreground block">
                {doctor.slot_duration_minutes} mins / patient
              </span>
              <span className="text-[11px] text-muted-foreground block">
                Cap: {doctor.max_daily_appointments} slots/day
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Section 2: Month Calendar with Overrides */}
      <Card className="p-5 border-border bg-card space-y-4">
        {/* Month Header Navigation */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-foreground">{monthLabel}</h2>
            <Badge variant="outline" className="text-xs">
              {overrides.length} {overrides.length === 1 ? "override" : "overrides"}
            </Badge>
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePrevMonth}
              className="h-8 w-8 p-0 cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
              <span className="sr-only">Previous Month</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setCurrentYear(2026);
                setCurrentMonth(9); // Oct 2026
              }}
              className="h-8 px-2.5 text-xs cursor-pointer"
            >
              Oct 2026 (Seed)
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleNextMonth}
              className="h-8 w-8 p-0 cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
              <span className="sr-only">Next Month</span>
            </Button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1 pb-2 border-b border-border/60">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-emerald-500/20 border border-emerald-500/40 inline-block" />
            <span>Regular OPD Day</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-destructive/20 border border-destructive/40 inline-block" />
            <span className="font-semibold text-destructive">Leave / Closed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-primary/20 border border-primary/40 inline-block" />
            <span className="font-semibold text-primary">Custom Shift Hours</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-muted border border-border inline-block" />
            <span>Regular Weekly Off</span>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-2">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((dayName) => (
            <div
              key={dayName}
              className="text-center font-bold text-xs py-1.5 text-muted-foreground uppercase tracking-wider"
            >
              {dayName}
            </div>
          ))}

          {calendarDays.map((cell) => {
            const isRegularWorkDay = doctor.available_days.includes(cell.weekdayIso);
            const override = overrides.find((o) => o.date === cell.dateStr);

            return (
              <button
                key={cell.dateStr}
                type="button"
                onClick={() => handleOpenAddOverride(cell.dateStr)}
                className={`min-h-[85px] p-2 rounded-lg border text-left flex flex-col justify-between transition-all cursor-pointer relative group ${
                  !cell.isCurrentMonth
                    ? "opacity-35 bg-muted/20 border-border/40"
                    : override
                    ? !override.is_available
                      ? "bg-destructive/10 border-destructive/30 hover:bg-destructive/20"
                      : "bg-primary/10 border-primary/30 hover:bg-primary/20"
                    : isRegularWorkDay
                    ? "bg-card border-border hover:border-primary/50 hover:bg-muted/40"
                    : "bg-muted/30 border-border/50 opacity-70"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-xs font-bold ${
                      override
                        ? !override.is_available
                          ? "text-destructive"
                          : "text-primary"
                        : "text-foreground"
                    }`}
                  >
                    {cell.dayNumber}
                  </span>

                  {override && (
                    <span
                      className={`w-2 h-2 rounded-full ${
                        !override.is_available ? "bg-destructive" : "bg-primary"
                      }`}
                    />
                  )}
                </div>

                <div className="mt-1 space-y-1">
                  {override ? (
                    !override.is_available ? (
                      <div className="p-1 rounded bg-destructive/15 text-destructive text-[10px] font-semibold leading-tight">
                        <span className="block truncate">On Leave</span>
                        {override.override_reason && (
                          <span className="block truncate text-[9px] opacity-80 font-normal">
                            {override.override_reason}
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="p-1 rounded bg-primary/15 text-primary text-[10px] font-semibold leading-tight">
                        <span className="block truncate">
                          {formatSlotTime(override.start_time)}
                        </span>
                        <span className="block truncate text-[9px] opacity-80 font-normal">
                          Custom Shift
                        </span>
                      </div>
                    )
                  ) : isRegularWorkDay ? (
                    <div className="text-[10px] text-muted-foreground">
                      <span className="block font-medium text-emerald-600 dark:text-emerald-400">
                        OPD
                      </span>
                      <span className="block text-[9px] truncate">
                        {formatSlotTime(doctor.slot_start_time)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[10px] text-muted-foreground/60 block">Off</span>
                  )}
                </div>

                <span className="sr-only">Click to edit schedule override for {cell.dateStr}</span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Section 3: Month Overrides Table */}
      <Card className="p-5 border-border bg-card space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-border/70">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">
              Overrides in {monthLabel}
            </h3>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleOpenAddOverride()}
            className="text-xs h-8 cursor-pointer gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Override</span>
          </Button>
        </div>

        {overrides.length === 0 ? (
          <p className="text-xs text-muted-foreground py-4 text-center">
            No schedule overrides recorded for {monthLabel}. The doctor adheres to the standard weekly template.
          </p>
        ) : (
          <div className="divide-y divide-border/60">
            {overrides.map((ov) => (
              <div
                key={ov.id}
                className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                      !ov.is_available
                        ? "bg-destructive/15 text-destructive"
                        : "bg-primary/15 text-primary"
                    }`}
                  >
                    {!ov.is_available ? <Ban className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-foreground text-sm">{ov.date}</span>
                      <Badge
                        variant="outline"
                        className={
                          !ov.is_available
                            ? "bg-destructive/10 text-destructive border-destructive/20 text-[10px]"
                            : "bg-primary/10 text-primary border-primary/20 text-[10px]"
                        }
                      >
                        {!ov.is_available ? "On Leave / Unavailable" : "Custom Working Hours"}
                      </Badge>
                    </div>

                    <p className="text-muted-foreground mt-0.5">
                      {!ov.is_available ? (
                        <span>Doctor will not accept appointments. Reason: {ov.override_reason || "None specified"}</span>
                      ) : (
                        <span>
                          Hours: {formatSlotTime(ov.start_time)} – {formatSlotTime(ov.end_time)} ({ov.override_reason || "Custom Shift"})
                        </span>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenAddOverride(ov.date)}
                    className="h-8 px-2.5 text-xs cursor-pointer gap-1"
                  >
                    <Edit2 className="w-3 h-3" />
                    <span>Edit</span>
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteOverride(ov.date)}
                    className="h-8 px-2 text-xs text-destructive hover:bg-destructive/10 cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span className="sr-only">Delete</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Add / Edit Override Dialog */}
      <ScheduleOverrideDialog
        open={overrideDialogOpen}
        onOpenChange={setOverrideDialogOpen}
        doctorId={doctor.id}
        doctorName={doctor.name}
        defaultDate={selectedDate}
        existingOverride={activeOverride}
        onSuccess={fetchOverrides}
      />

      {/* Edit Weekly Template Dialog */}
      <Dialog open={templateModalOpen} onOpenChange={setTemplateModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <form onSubmit={handleSaveTemplate}>
            <DialogHeader>
              <DialogTitle className="text-base font-bold">
                Edit Weekly Schedule Template
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update regular working days, shift hours, and patient capacity for {doctor.name}.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-3 text-xs">
              {/* Working days toggle */}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Working Days</Label>
                <div className="flex flex-wrap gap-1.5">
                  {WEEKDAYS.map((wd) => {
                    const isSelected = templateDays.includes(wd.day);
                    return (
                      <button
                        key={wd.day}
                        type="button"
                        onClick={() => {
                          if (isSelected) {
                            setTemplateDays(templateDays.filter((d) => d !== wd.day));
                          } else {
                            setTemplateDays([...templateDays, wd.day].sort());
                          }
                        }}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-semibold cursor-pointer transition-all ${
                          isSelected
                            ? "bg-primary text-primary-foreground border-primary"
                            : "bg-muted border-border text-muted-foreground hover:bg-muted/80"
                        }`}
                      >
                        {wd.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Shift Hours */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="template-start" className="text-xs font-semibold">
                    Start Time
                  </Label>
                  <Input
                    id="template-start"
                    type="time"
                    value={templateStart}
                    onChange={(e) => setTemplateStart(e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="template-end" className="text-xs font-semibold">
                    End Time
                  </Label>
                  <Input
                    id="template-end"
                    type="time"
                    value={templateEnd}
                    onChange={(e) => setTemplateEnd(e.target.value)}
                    required
                  />
                </div>
              </div>

              {/* Slot length and max daily */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="template-duration" className="text-xs font-semibold">
                    Slot Duration (minutes)
                  </Label>
                  <Input
                    id="template-duration"
                    type="number"
                    min="5"
                    max="120"
                    step="5"
                    value={templateDuration}
                    onChange={(e) => setTemplateDuration(parseInt(e.target.value, 10))}
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="template-max" className="text-xs font-semibold">
                    Max Daily Appointments
                  </Label>
                  <Input
                    id="template-max"
                    type="number"
                    min="1"
                    max="100"
                    value={templateMaxDaily}
                    onChange={(e) => setTemplateMaxDaily(parseInt(e.target.value, 10))}
                    required
                  />
                </div>
              </div>
            </div>

            <DialogFooter className="border-t border-border pt-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setTemplateModalOpen(false)}
                className="cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isSavingTemplate}
                className="gap-1.5 cursor-pointer"
              >
                {isSavingTemplate ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Save Template</span>
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
