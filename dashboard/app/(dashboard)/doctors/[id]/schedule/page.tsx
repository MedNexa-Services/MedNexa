"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  deleteScheduleOverride,
  getDoctor,
  listScheduleOverrides,
  type DoctorDetailOut,
  type ScheduleOverrideOut,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { todayIn } from "@/lib/dates";
import { formatDate, formatTime } from "@/lib/format";
import { WEEKDAYS, describeDays } from "@/lib/weekdays";
import { PageHeader } from "@/components/page-header";
import { BackLink } from "@/components/detail-list";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { DoctorFormDialog } from "@/components/doctors/DoctorFormDialog";
import { ScheduleOverrideDialog } from "@/components/doctors/ScheduleOverrideDialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const pad = (n: number) => String(n).padStart(2, "0");

function monthGrid(year: number, month: number): (string | null)[] {
  const first = new Date(Date.UTC(year, month, 1));
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const lead = (first.getUTCDay() + 6) % 7;
  const cells: (string | null)[] = Array(lead).fill(null);
  for (let d = 1; d <= days; d++) cells.push(`${year}-${pad(month + 1)}-${pad(d)}`);
  while (cells.length % 7) cells.push(null);
  return cells;
}

export default function DoctorSchedulePage() {
  const { id } = useParams<{ id: string }>();
  const { hospital } = useHospital();
  const today = todayIn(hospital?.timezone);
  const [doctor, setDoctor] = React.useState<DoctorDetailOut | null>(null);
  const [overrides, setOverrides] = React.useState<ScheduleOverrideOut[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [month, setMonth] = React.useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });

  const [hoursOpen, setHoursOpen] = React.useState(false);
  const [overrideDate, setOverrideDate] = React.useState<string | null | undefined>(undefined);
  const [removing, setRemoving] = React.useState<ScheduleOverrideOut | null>(null);

  const loadDoctor = React.useCallback(async () => {
    try {
      setDoctor(await getDoctor(id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "The doctor could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadOverrides = React.useCallback(async () => {
    const { year, month: m } = month;
    const last = new Date(Date.UTC(year, m + 1, 0)).getUTCDate();
    try {
      setOverrides(
        await listScheduleOverrides(id, { from: `${year}-${pad(m + 1)}-01`, to: `${year}-${pad(m + 1)}-${last}` })
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Leave and changed hours could not be loaded.");
    }
  }, [id, month]);

  React.useEffect(() => {
    loadDoctor();
  }, [loadDoctor]);
  React.useEffect(() => {
    loadOverrides();
  }, [loadOverrides]);

  const back = <BackLink href={`/doctors/${id}`}>{doctor?.name ?? "Doctor"}</BackLink>;
  if (loading) return <div className="h-96 animate-pulse rounded-lg border border-border bg-card" />;
  if (!doctor) return <PageHeader back={<BackLink href="/doctors">Doctors</BackLink>} title="Doctor not found" />;

  const byDate = new Map(overrides.map((o) => [o.date, o]));
  const cells = monthGrid(month.year, month.month);
  const monthLabel = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(
    new Date(month.year, month.month, 1)
  );
  const shiftMonth = (delta: number) =>
    setMonth(({ year, month: m }) => {
      const d = new Date(year, m + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });

  return (
    <>
      <PageHeader
        back={back}
        title="Schedule and leave"
        description={doctor.name}
        actions={
          <Button onClick={() => setOverrideDate(null)}>
            <Plus /> Add leave or changed hours
          </Button>
        }
      />

      <section className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-card px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-[15px] font-semibold">Usual week</h2>
          <p className="text-sm text-muted-foreground">
            {describeDays(doctor.available_days)}, <time>{formatTime(doctor.slot_start_time)}</time> to{" "}
            <time>{formatTime(doctor.slot_end_time)}</time>. {doctor.slot_duration_minutes} minutes per patient, up to{" "}
            {doctor.max_daily_appointments} a day.
          </p>
        </div>
        <Button variant="outline" onClick={() => setHoursOpen(true)}>
          Edit usual week
        </Button>
      </section>

      <section className="rounded-lg border border-border bg-card">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-[15px] font-semibold">{monthLabel}</h2>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => shiftMonth(-1)} aria-label="Previous month">
              <ChevronLeft />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const now = new Date();
                setMonth({ year: now.getFullYear(), month: now.getMonth() });
              }}
            >
              This month
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => shiftMonth(1)} aria-label="Next month">
              <ChevronRight />
            </Button>
          </div>
        </header>

        <div className="grid grid-cols-7 border-b border-border text-center text-[13px] text-muted-foreground">
          {WEEKDAYS.map((w) => (
            <div key={w.day} className="py-2">
              <span className="hidden sm:inline">{w.short}</span>
              <span className="sm:hidden">{w.short[0]}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 [&>*:nth-child(7n)]:border-r-0">
          {cells.map((date, i) => {
            if (!date) return <div key={`blank-${i}`} className="min-h-20 border-r border-b border-border bg-muted/30" />;
            const override = byDate.get(date);
            const weekday = ((i % 7) + 1) as number;
            const usual = doctor.available_days.includes(weekday);
            const past = date < today;
            return (
              <button
                key={date}
                type="button"
                disabled={past}
                onClick={() => setOverrideDate(date)}
                aria-label={`${formatDate(date)}: ${
                  override ? (override.is_available ? "changed hours" : "not working") : usual ? "usual hours" : "day off"
                }`}
                className={cn(
                  "flex min-h-20 cursor-pointer flex-col items-start gap-1 border-r border-b border-border p-2 text-left text-[13px] hover:bg-muted/50 disabled:cursor-default disabled:hover:bg-transparent",
                  past && "text-muted-foreground/60",
                  date === today && "shadow-[inset_0_2px_0_var(--primary)]"
                )}
              >
                <span className={cn("tabular", date === today && "font-semibold text-primary")}>
                  {Number(date.slice(8))}
                </span>
                {override ? (
                  override.is_available ? (
                    <span className="text-status-moved">
                      {formatTime(override.start_time ?? doctor.slot_start_time)}–
                      {formatTime(override.end_time ?? doctor.slot_end_time)}
                    </span>
                  ) : (
                    <span className="text-status-cancelled">{override.override_reason || "Not working"}</span>
                  )
                ) : (
                  !usual && <span className="text-muted-foreground">Off</span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {overrides.length > 0 && (
        <section className="mt-6 rounded-lg border border-border bg-card">
          <h2 className="border-b border-border px-4 py-3 text-[15px] font-semibold">Changes this month</h2>
          <ul className="divide-y divide-border">
            {overrides.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
                <span>
                  <span className="font-medium">{formatDate(o.date)}</span>
                  <span className="text-muted-foreground">
                    {": "}
                    {o.is_available
                      ? `${formatTime(o.start_time ?? doctor.slot_start_time)} to ${formatTime(o.end_time ?? doctor.slot_end_time)}`
                      : "not working"}
                    {o.override_reason && ` (${o.override_reason})`}
                  </span>
                </span>
                {o.date >= today && (
                  <span className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setOverrideDate(o.date)}>
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setRemoving(o)}
                    >
                      Remove
                    </Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <DoctorFormDialog open={hoursOpen} onOpenChange={setHoursOpen} doctor={doctor} onSuccess={loadDoctor} />
      <ScheduleOverrideDialog
        open={overrideDate !== undefined}
        onOpenChange={(open) => !open && setOverrideDate(undefined)}
        doctorId={doctor.id}
        doctorName={doctor.name}
        defaultDate={overrideDate ?? undefined}
        existingOverride={overrideDate ? byDate.get(overrideDate) : null}
        onSuccess={() => {
          loadOverrides();
          loadDoctor();
        }}
      />
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Remove the change on ${removing ? formatDate(removing.date) : ""}?`}
        description="The doctor goes back to their usual hours that day, and those slots can be booked again."
        confirmLabel="Remove"
        onConfirm={async () => {
          if (!removing) return;
          try {
            await deleteScheduleOverride(doctor.id, removing.date);
            toast.success("Usual hours restored");
            loadOverrides();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "The change could not be removed.");
          }
        }}
      />
    </>
  );
}
