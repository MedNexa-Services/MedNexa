"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { toast } from "sonner";
import {
  listAppointments,
  listDoctors,
  type AppointmentOut,
  type AppointmentStatus,
  type DoctorOut,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { addDays, todayIn } from "@/lib/dates";
import { formatDate, formatTime } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { APPOINTMENT_STATUS_LABELS, AppointmentStatusLabel, BookingSourceLabel } from "@/components/status";
import { BookAppointmentDialog } from "@/components/appointments/BookAppointmentDialog";
import { CancelAppointmentDialog } from "@/components/appointments/CancelAppointmentDialog";
import { RescheduleAppointmentDialog } from "@/components/appointments/RescheduleAppointmentDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

export default function AppointmentsPage() {
  const { hospitalId, hospital } = useHospital();
  const today = todayIn(hospital?.timezone);

  const [pickedDate, setPickedDate] = React.useState<string | null>(null);
  const date = pickedDate ?? today;
  const [doctorId, setDoctorId] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(0);

  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [total, setTotal] = React.useState(0);
  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [loading, setLoading] = React.useState(true);

  const [bookOpen, setBookOpen] = React.useState(false);
  const [cancelTarget, setCancelTarget] = React.useState<AppointmentOut | null>(null);
  const [moveTarget, setMoveTarget] = React.useState<AppointmentOut | null>(null);

  React.useEffect(() => {
    if (!hospitalId) return;
    listDoctors({ hospital_id: hospitalId, limit: 200, include_inactive: true })
      .then((res) => setDoctors(res.items))
      .catch(() => toast.error("The doctor list could not be loaded."));
  }, [hospitalId]);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = React.useCallback(async () => {
    if (!hospitalId) return;
    try {
      const res = await listAppointments({
        hospital_id: hospitalId,
        date: date || undefined,
        doctor_id: doctorId || undefined,
        status: (status || undefined) as AppointmentStatus | undefined,
        q: query || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setAppointments(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Appointments could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [hospitalId, date, doctorId, status, query, page]);

  React.useEffect(() => {
    load();
  }, [load]);

  const filtered = Boolean(doctorId || status || query || pickedDate !== null);
  const changeFilter = (apply: () => void) => {
    apply();
    setPage(0);
  };

  const dayOptions = [
    { label: "Today", value: today },
    { label: "Tomorrow", value: addDays(today, 1) },
    { label: "All dates", value: "" },
  ];

  return (
    <>
      <PageHeader
        title="Appointments"
        description={date ? `Showing ${formatDate(date)}` : "Showing every date"}
        actions={
          <Button onClick={() => setBookOpen(true)}>
            <Plus /> Book appointment
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-border bg-card p-0.5 text-sm" role="group" aria-label="Date">
          {dayOptions.map((option) => (
            <button
              key={option.label}
              type="button"
              aria-pressed={date === option.value}
              onClick={() => changeFilter(() => setPickedDate(option.value === today ? null : option.value))}
              className={cn(
                "cursor-pointer rounded px-3 py-1",
                date === option.value
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground"
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
          onChange={(e) => changeFilter(() => setPickedDate(e.target.value))}
          className="h-8 w-auto bg-card"
        />
        <NativeSelect
          aria-label="Doctor"
          value={doctorId}
          onChange={(e) => changeFilter(() => setDoctorId(e.target.value))}
          className="w-48"
        >
          <option value="">All doctors</option>
          {doctors.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label="Status"
          value={status}
          onChange={(e) => changeFilter(() => setStatus(e.target.value))}
          className="w-36"
        >
          <option value="">Any status</option>
          {Object.entries(APPOINTMENT_STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </NativeSelect>
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label="Search appointments"
            placeholder="Patient name, phone or token"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 bg-card pl-8"
          />
        </div>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              changeFilter(() => {
                setPickedDate(null);
                setDoctorId("");
                setStatus("");
                setSearch("");
                setQuery("");
              })
            }
          >
            Reset filters
          </Button>
        )}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {loading ? (
          <div className="h-72 animate-pulse" />
        ) : appointments.length === 0 ? (
          <div className="px-6 py-10">
            <p className="text-sm font-semibold">No appointments match</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {query
                ? `Nothing found for "${query}". Check the spelling, or search by phone number.`
                : "Try another date or doctor, or book one now."}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-16">Token</TableHead>
                <TableHead>When</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Doctor</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Booked via</TableHead>
                <TableHead className="text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {appointments.map((appt) => (
                <TableRow key={appt.id}>
                  <TableCell className="text-base font-semibold">{appt.token_number}</TableCell>
                  <TableCell>
                    <time className="block">{formatTime(appt.appointment_time)}</time>
                    {!date && (
                      <span className="text-[13px] text-muted-foreground">{formatDate(appt.appointment_date)}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Link href={`/appointments/${appt.id}`} className="font-medium hover:underline">
                      {appt.patient_name}
                    </Link>
                    <span className="block text-[13px] text-muted-foreground">{appt.patient_phone}</span>
                  </TableCell>
                  <TableCell>
                    <span className="block">{appt.doctor_name}</span>
                    <span className="text-[13px] text-muted-foreground">{appt.department}</span>
                  </TableCell>
                  <TableCell>
                    <AppointmentStatusLabel status={appt.status} />
                  </TableCell>
                  <TableCell>
                    <BookingSourceLabel source={appt.booking_source} />
                  </TableCell>
                  <TableCell className="text-right">
                    {appt.status === "BOOKED" && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setMoveTarget(appt)}>
                          Reschedule
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setCancelTarget(appt)}
                        >
                          Cancel
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </div>

      <BookAppointmentDialog
        open={bookOpen}
        onOpenChange={setBookOpen}
        defaultDate={date || undefined}
        defaultDoctorId={doctorId || undefined}
        onSuccess={load}
      />
      <CancelAppointmentDialog
        open={!!cancelTarget}
        onOpenChange={(open) => !open && setCancelTarget(null)}
        appointment={cancelTarget}
        onSuccess={load}
      />
      <RescheduleAppointmentDialog
        open={!!moveTarget}
        onOpenChange={(open) => !open && setMoveTarget(null)}
        appointment={moveTarget}
        onSuccess={load}
      />
    </>
  );
}
