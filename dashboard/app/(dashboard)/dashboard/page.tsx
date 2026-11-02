"use client";

import * as React from "react";
import Link from "next/link";
import { Phone, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  fetchAllPages,
  getDoctorSlots,
  listAppointments,
  listDoctors,
  listScheduleOverrides,
  type AppointmentOut,
  type DoctorOut,
  type ScheduleOverrideOut,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { addDays, isoWeekday, todayIn } from "@/lib/dates";
import { formatDate, formatTime } from "@/lib/format";
import { PageHeader, StatStrip } from "@/components/page-header";
import { BookAppointmentDialog } from "@/components/appointments/BookAppointmentDialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const IN_QUEUE = new Set(["BOOKED", "COMPLETED", "NO_SHOW"]);

interface DoctorDay {
  doctor: DoctorOut;
  onDuty: boolean;
  start: string;
  end: string;
  leaveReason: string | null;
  openSlots: number;
  queue: AppointmentOut[];
}

function dayFor(
  doctor: DoctorOut,
  date: string,
  override: ScheduleOverrideOut | undefined
): Pick<DoctorDay, "onDuty" | "start" | "end" | "leaveReason"> {
  if (override) {
    return {
      onDuty: override.is_available,
      start: override.start_time ?? doctor.slot_start_time,
      end: override.end_time ?? doctor.slot_end_time,
      leaveReason: override.is_available ? null : (override.override_reason ?? "On leave"),
    };
  }
  return {
    onDuty: doctor.available_days.includes(isoWeekday(date)),
    start: doctor.slot_start_time,
    end: doctor.slot_end_time,
    leaveReason: null,
  };
}

function nowIn(timeZone?: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hour12: false }).format(
      new Date()
    );
  } catch {
    return new Date().toTimeString().slice(0, 5);
  }
}

export default function TodayPage() {
  const { hospital, hospitalId } = useHospital();
  const today = todayIn(hospital?.timezone);
  const [pickedDate, setPickedDate] = React.useState<string | null>(null);
  const date = pickedDate ?? today;

  const [days, setDays] = React.useState<DoctorDay[]>([]);
  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [doctorCount, setDoctorCount] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [bookingOpen, setBookingOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    if (!hospitalId) return;
    try {
      const [appts, doctors] = await Promise.all([
        fetchAllPages((limit, offset) => listAppointments({ hospital_id: hospitalId, date, limit, offset })),
        listDoctors({ hospital_id: hospitalId, limit: 200 }),
      ]);
      const perDoctor = await Promise.all(
        doctors.items.map(async (doctor) => {
          const [overrides, slots] = await Promise.all([
            listScheduleOverrides(doctor.id, { from: date, to: date }),
            getDoctorSlots(doctor.id, date),
          ]);
          const queue = appts.items
            .filter((a) => a.doctor_id === doctor.id && IN_QUEUE.has(a.status))
            .sort((a, b) => a.appointment_time.localeCompare(b.appointment_time));
          const booked = queue.filter((a) => a.status === "BOOKED").length;
          return {
            doctor,
            ...dayFor(doctor, date, overrides[0]),
            openSlots: Math.min(slots.length, Math.max(0, doctor.max_daily_appointments - booked)),
            queue,
          };
        })
      );
      setAppointments(appts.items);
      setDoctorCount(doctors.total);
      setDays(perDoctor.filter((d) => d.onDuty || d.queue.length > 0));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Today's queue could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [hospitalId, date]);

  React.useEffect(() => {
    load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, [load]);

  const booked = appointments.filter((a) => a.status === "BOOKED");
  const isToday = date === today;
  const now = nowIn(hospital?.timezone);

  return (
    <>
      <PageHeader
        title={isToday ? "Today" : formatDate(date)}
        description={
          isToday
            ? formatDate(date)
            : date === addDays(today, 1)
              ? "Tomorrow"
              : "Queue for another day"
        }
        actions={
          <>
            <div className="flex rounded-md border border-border bg-card p-0.5 text-sm" role="group" aria-label="Day">
              {[
                { label: "Today", value: today },
                { label: "Tomorrow", value: addDays(today, 1) },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setPickedDate(option.value === today ? null : option.value)}
                  aria-pressed={date === option.value}
                  className={cn(
                    "cursor-pointer rounded px-3 py-1",
                    date === option.value ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <Input
              type="date"
              aria-label="Pick a date"
              value={date}
              onChange={(e) => e.target.value && setPickedDate(e.target.value === today ? null : e.target.value)}
              className="h-8 w-auto bg-card"
            />
            <Button onClick={() => setBookingOpen(true)}>
              <Plus /> Book appointment
            </Button>
          </>
        }
      />

      <StatStrip
        items={[
          { label: "Booked", value: loading ? "–" : booked.length },
          { label: "Open slots", value: loading ? "–" : days.reduce((n, d) => n + d.openSlots, 0) },
          { label: "Doctors on duty", value: loading ? "–" : days.filter((d) => d.onDuty).length },
          {
            label: "Booked by phone",
            value: loading ? "–" : booked.filter((a) => a.booking_source === "AI_CALL").length,
          },
          {
            label: "Cancelled",
            value: loading ? "–" : appointments.filter((a) => a.status === "CANCELLED").length,
          },
        ]}
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-64 animate-pulse rounded-lg border border-border bg-card" />
          ))}
        </div>
      ) : days.length === 0 ? (
        <div className="rounded-lg border border-border bg-card px-6 py-10">
          {doctorCount === 0 ? (
            <>
              <h2 className="text-sm font-semibold">Add your doctors</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Patients can book, at the desk or by phone, once doctors and their hours are added.
              </p>
              <Link href="/doctors" className={cn(buttonVariants({ size: "sm" }), "mt-4")}>
                Add doctors
              </Link>
            </>
          ) : (
            <>
              <h2 className="text-sm font-semibold">No doctors are seeing patients on {formatDate(date)}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Doctors&apos; working days and leave are set on their schedule page.
              </p>
              <Link href="/doctors" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-4")}>
                Go to doctors
              </Link>
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {days.map((day) => {
            const next = isToday
              ? day.queue.find((a) => a.status === "BOOKED" && a.appointment_time.slice(0, 5) >= now)
              : undefined;
            return (
              <section key={day.doctor.id} className="flex flex-col rounded-lg border border-border bg-card">
                <header className="border-b border-border px-4 py-3">
                  <Link href={`/doctors/${day.doctor.id}`} className="font-semibold hover:underline">
                    {day.doctor.name}
                  </Link>
                  <p className="text-[13px] text-muted-foreground">
                    {day.doctor.speciality}
                    {day.onDuty && (
                      <>
                        , <time>{formatTime(day.start)}</time> to <time>{formatTime(day.end)}</time>
                      </>
                    )}
                  </p>
                  <p className="tabular mt-2 text-[13px]">
                    {day.onDuty ? (
                      <>
                        <span className="font-medium">{day.queue.length}</span> of{" "}
                        {day.doctor.max_daily_appointments} booked
                        <span className="text-muted-foreground">
                          {day.openSlots > 0 ? `, ${day.openSlots} open` : ", no slots left"}
                        </span>
                      </>
                    ) : (
                      <span className="text-status-cancelled">{day.leaveReason ?? "Not working this day"}</span>
                    )}
                  </p>
                </header>

                {day.queue.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted-foreground">No patients booked yet.</p>
                ) : (
                  <ol className="divide-y divide-border">
                    {day.queue.map((appt) => {
                      const done = appt.status !== "BOOKED";
                      const isNext = appt.id === next?.id;
                      return (
                        <li key={appt.id}>
                          <Link
                            href={`/appointments/${appt.id}`}
                            className={cn(
                              "grid grid-cols-[3.25rem_1fr_auto] items-center gap-3 px-4 py-2.5 hover:bg-muted/60",
                              isNext && "bg-accent/60 shadow-[inset_2px_0_0_var(--primary)]"
                            )}
                          >
                            <span
                              className={cn(
                                "tabular text-[26px] leading-none font-semibold tracking-tight",
                                done ? "text-muted-foreground/60" : "text-foreground"
                              )}
                              aria-label={`Token ${appt.token_number}`}
                            >
                              {appt.token_number}
                            </span>
                            <span className="min-w-0">
                              <span className={cn("block truncate text-sm font-medium", done && "text-muted-foreground")}>
                                {appt.patient_name}
                              </span>
                              <span className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                                <time>{formatTime(appt.appointment_time)}</time>
                                {appt.booking_source === "AI_CALL" && (
                                  <Phone className="size-3" aria-label="Booked by phone" />
                                )}
                                {appt.status === "NO_SHOW" && "No-show"}
                                {appt.status === "COMPLETED" && "Seen"}
                              </span>
                            </span>
                            {isNext && <span className="text-xs font-medium text-primary">Next</span>}
                          </Link>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </section>
            );
          })}
        </div>
      )}

      <BookAppointmentDialog
        open={bookingOpen}
        onOpenChange={setBookingOpen}
        defaultDate={date}
        onSuccess={() => {
          setBookingOpen(false);
          load();
        }}
      />
    </>
  );
}
