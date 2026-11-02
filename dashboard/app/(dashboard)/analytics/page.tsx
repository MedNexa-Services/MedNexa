"use client";

import * as React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import {
  fetchAllPages,
  listAppointments,
  listCalls,
  type AppointmentOut,
  type AppointmentStatus,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { addDays, isoWeekday, todayIn } from "@/lib/dates";
import { formatDate } from "@/lib/format";
import { WEEKDAYS } from "@/lib/weekdays";
import { PageHeader, StatStrip } from "@/components/page-header";
import { APPOINTMENT_STATUS_LABELS } from "@/components/status";
import { cn } from "@/lib/utils";

type Range = "7" | "30" | "next30" | "90";
const RANGES: { value: Range; label: string }[] = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
  { value: "next30", label: "Next 30 days" },
];

const STATUS_TONE: Record<AppointmentStatus, string> = {
  BOOKED: "bg-status-booked",
  COMPLETED: "bg-status-done",
  CANCELLED: "bg-status-cancelled",
  RESCHEDULED: "bg-status-moved",
  NO_SHOW: "bg-status-moved",
};

const percent = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "–");

function hourLabel(hour: number) {
  return `${hour % 12 || 12} ${hour >= 12 ? "PM" : "AM"}`;
}

function BarPanel({
  title,
  description,
  data,
  unit,
}: {
  title: string;
  description: string;
  data: { label: string; value: number }[];
  unit: string;
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-4 py-3">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        <p className="text-[13px] text-muted-foreground">{description}</p>
      </header>
      <div className="h-56 px-2 pt-4 pb-2" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barCategoryGap={6}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
              interval="preserveStartEnd"
            />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              formatter={(value) => [`${value} ${unit}`, ""]}
              separator=""
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 13,
                color: "var(--popover-foreground)",
              }}
              labelStyle={{ color: "var(--muted-foreground)" }}
            />
            <Bar dataKey="value" fill="var(--chart-1)" radius={[4, 4, 0, 0]} maxBarSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <th scope="row">{d.label}</th>
              <td>
                {d.value} {unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function BarList({
  title,
  rows,
}: {
  title: string;
  rows: { key: string; label: React.ReactNode; value: number; tone?: string }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <section className="rounded-lg border border-border bg-card">
      <h2 className="border-b border-border px-4 py-3 text-[15px] font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">No appointments in this period.</p>
      ) : (
        <ul className="space-y-3 px-4 py-4">
          {rows.map((row) => (
            <li key={row.key} className="grid grid-cols-[minmax(0,11rem)_1fr_2.5rem] items-center gap-3 text-sm">
              <span className="truncate">{row.label}</span>
              <span className="h-2 rounded-full bg-muted">
                <span
                  className={cn("block h-2 rounded-full", row.tone ?? "bg-chart-1")}
                  style={{ width: `${(row.value / max) * 100}%` }}
                />
              </span>
              <span className="tabular text-right text-muted-foreground">{row.value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function AnalyticsPage() {
  const { hospitalId, hospital } = useHospital();
  const today = todayIn(hospital?.timezone);
  const [range, setRange] = React.useState<Range>("30");
  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [truncated, setTruncated] = React.useState(false);
  const [calls, setCalls] = React.useState({ total: 0, escalated: 0 });
  const [loading, setLoading] = React.useState(true);

  const [from, to] =
    range === "next30" ? [today, addDays(today, 30)] : [addDays(today, -Number(range)), today];

  React.useEffect(() => {
    if (!hospitalId) return;
    let cancelled = false;
    const started_after = new Date(`${from}T00:00:00`).toISOString();
    const started_before = new Date(`${addDays(to, 1)}T00:00:00`).toISOString();
    (async () => {
      try {
        const [appts, allCalls, escalated] = await Promise.all([
          fetchAllPages((limit, offset) =>
            listAppointments({ hospital_id: hospitalId, date_from: from, date_to: to, limit, offset })
          ),
          listCalls({ hospital_id: hospitalId, started_after, started_before, limit: 1 }),
          listCalls({ hospital_id: hospitalId, started_after, started_before, escalated: true, limit: 1 }),
        ]);
        if (cancelled) return;
        setAppointments(appts.items);
        setTruncated(appts.truncated);
        setCalls({ total: allCalls.total, escalated: escalated.total });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Analytics could not be loaded.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hospitalId, from, to]);

  const kept = appointments.filter((a) => a.status !== "RESCHEDULED");
  const byPhone = kept.filter((a) => a.booking_source === "AI_CALL").length;
  const cancelled = kept.filter((a) => a.status === "CANCELLED").length;
  const visits = kept.filter((a) => a.status !== "CANCELLED");

  const weekdayData = WEEKDAYS.map((w) => ({
    label: w.short,
    value: visits.filter((a) => isoWeekday(a.appointment_date) === w.day).length,
  }));

  const hours = visits.map((a) => Number(a.appointment_time.slice(0, 2)));
  const hourData =
    hours.length === 0
      ? []
      : Array.from({ length: Math.max(...hours) - Math.min(...hours) + 1 }, (_, i) => {
          const hour = Math.min(...hours) + i;
          return { label: hourLabel(hour), value: hours.filter((h) => h === hour).length };
        });

  const perDoctor = new Map<string, { name: string; department: string; value: number }>();
  for (const a of visits) {
    const entry = perDoctor.get(a.doctor_id) ?? { name: a.doctor_name, department: a.department, value: 0 };
    entry.value += 1;
    perDoctor.set(a.doctor_id, entry);
  }
  const doctorRows = [...perDoctor.entries()]
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, 8)
    .map(([id, d]) => ({ key: id, label: d.name, value: d.value }));

  const statusRows = (Object.keys(APPOINTMENT_STATUS_LABELS) as AppointmentStatus[])
    .map((status) => ({
      key: status,
      label: APPOINTMENT_STATUS_LABELS[status],
      value: appointments.filter((a) => a.status === status).length,
      tone: STATUS_TONE[status],
    }))
    .filter((row) => row.value > 0);

  return (
    <>
      <PageHeader
        title="Analytics"
        description={`${formatDate(from)} to ${formatDate(to)}`}
        actions={
          <div className="flex rounded-md border border-border bg-card p-0.5 text-sm" role="group" aria-label="Period">
            {RANGES.map((r) => (
              <button
                key={r.value}
                type="button"
                aria-pressed={range === r.value}
                onClick={() => setRange(r.value)}
                className={cn(
                  "cursor-pointer rounded px-3 py-1",
                  range === r.value ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      />

      {truncated && (
        <p className="mb-4 text-sm text-status-moved">
          Only the first 2,000 appointments in this period are counted. Pick a shorter period for exact figures.
        </p>
      )}

      <StatStrip
        items={[
          { label: "Appointments", value: loading ? "–" : kept.length },
          { label: "Booked by phone", value: loading ? "–" : byPhone, hint: !loading && percent(byPhone, kept.length) },
          { label: "Cancelled", value: loading ? "–" : cancelled, hint: !loading && percent(cancelled, kept.length) },
          { label: "Calls answered", value: loading ? "–" : calls.total },
          {
            label: "Passed to staff",
            value: loading ? "–" : calls.escalated,
            hint: !loading && percent(calls.escalated, calls.total),
          },
        ]}
      />

      {loading ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-72 animate-pulse rounded-lg border border-border bg-card" />
          ))}
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <BarPanel
            title="Busiest days"
            description="Appointments by weekday, not counting cancellations"
            data={weekdayData}
            unit="appointments"
          />
          <BarPanel
            title="Busiest hours"
            description="Appointments by start time, not counting cancellations"
            data={hourData}
            unit="appointments"
          />
          <BarList title="Appointments per doctor" rows={doctorRows} />
          <BarList title="How appointments ended up" rows={statusRows} />
        </div>
      )}
    </>
  );
}
