"use client";

import * as React from "react";
import {
  listAppointments,
  listDoctors,
  listCalls,
  fetchAllPages,
  type AppointmentOut,
  type DoctorOut,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { addDays, todayIn } from "@/lib/dates";
import { toast } from "sonner";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import {
  TrendingUp,
  BarChart3,
  PieChart as PieChartIcon,
  Calendar,
  Clock,
  UserCheck,
  PhoneCall,
  RefreshCw,
  AlertCircle,
  Filter,
  CheckCircle2,
  Ban,
  Activity,
  Bot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const STATUS_COLORS: Record<string, string> = {
  BOOKED: "#10b981", // Emerald 500
  CANCELLED: "#ef4444", // Red 500
  COMPLETED: "#3b82f6", // Blue 500
  RESCHEDULED: "#f59e0b", // Amber 500
  NO_SHOW: "#64748b", // Slate 500
};

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function AnalyticsPage() {
  const { hospitalId, hospital } = useHospital();

  const [dateRangePreset, setDateRangePreset] = React.useState<string>("all");
  const [dateFrom, setDateFrom] = React.useState<string>("");
  const [dateTo, setDateTo] = React.useState<string>("");

  const [appointments, setAppointments] = React.useState<AppointmentOut[]>([]);
  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [truncated, setTruncated] = React.useState(false);
  const [totalCalls, setTotalCalls] = React.useState(0);

  // Quick preset dates (relative to today in the hospital's timezone)
  const handlePresetChange = (preset: string) => {
    setDateRangePreset(preset);
    const today = todayIn(hospital?.timezone);
    if (preset === "7days") {
      setDateFrom(addDays(today, -7));
      setDateTo(today);
    } else if (preset === "30days") {
      setDateFrom(addDays(today, -30));
      setDateTo(today);
    } else if (preset === "next30") {
      setDateFrom(today);
      setDateTo(addDays(today, 30));
    } else if (preset === "all") {
      setDateFrom("");
      setDateTo("");
    }
  };

  const fetchData = React.useCallback(async () => {
    if (!hospitalId) return; // never aggregate across hospitals while the hospital is loading
    setIsLoading(true);
    try {
      const [aptRes, docRes, callRes] = await Promise.all([
        fetchAllPages((limit, offset) =>
          listAppointments({
            hospital_id: hospitalId,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            limit,
            offset,
          })
        ),
        listDoctors({ hospital_id: hospitalId, limit: 200 }),
        listCalls({ hospital_id: hospitalId, limit: 1 }),
      ]);

      setAppointments(aptRes.items);
      setTruncated(aptRes.truncated);
      setDoctors(docRes.items);
      setTotalCalls(callRes.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load analytics";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, dateFrom, dateTo]);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 1. Chart Data: Appointments by Day of Week
  const dayOfWeekData = React.useMemo(() => {
    const counts: Record<string, number> = {
      Mon: 0,
      Tue: 0,
      Wed: 0,
      Thu: 0,
      Fri: 0,
      Sat: 0,
      Sun: 0,
    };

    appointments.forEach((apt) => {
      try {
        const d = new Date(apt.appointment_date + "T00:00:00");
        const dayIdx = d.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
        const dayName = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][dayIdx];
        if (counts[dayName] !== undefined) {
          counts[dayName]++;
        }
      } catch {}
    });

    return DAYS_OF_WEEK.map((day) => ({
      day,
      appointments: counts[day] || 0,
    }));
  }, [appointments]);

  // 2. Chart Data: Status Breakdown
  const statusPieData = React.useMemo(() => {
    const map: Record<string, number> = {};
    appointments.forEach((apt) => {
      map[apt.status] = (map[apt.status] || 0) + 1;
    });

    const list = Object.keys(map).map((status) => ({
      name: status,
      value: map[status],
      color: STATUS_COLORS[status] || "#94a3b8",
    }));

    // If empty, return placeholder item so chart doesn't break
    if (list.length === 0) {
      return [{ name: "No Bookings", value: 1, color: "#cbd5e1" }];
    }
    return list;
  }, [appointments]);

  // 3. Chart Data: Top 5 Doctors by Bookings
  const topDoctorsData = React.useMemo(() => {
    const map: Record<string, { name: string; count: number; department: string }> = {};

    appointments.forEach((apt) => {
      if (!map[apt.doctor_id]) {
        map[apt.doctor_id] = {
          name: apt.doctor_name,
          count: 0,
          department: apt.department,
        };
      }
      map[apt.doctor_id].count++;
    });

    return Object.values(map)
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
      .map((d) => ({
        name: d.name.replace(/^Dr\.\s+/, ""), // cleaner label on chart
        bookings: d.count,
        department: d.department,
      }));
  }, [appointments]);

  // 4. Chart Data: Peak Booking Hours
  const hourlyData = React.useMemo(() => {
    const hoursMap: Record<number, number> = {
      9: 0,
      10: 0,
      11: 0,
      12: 0,
      13: 0,
      14: 0,
      15: 0,
      16: 0,
      17: 0,
      18: 0,
      19: 0,
    };

    appointments.forEach((apt) => {
      try {
        const hour = parseInt(apt.appointment_time.split(":")[0], 10);
        if (hoursMap[hour] !== undefined) {
          hoursMap[hour]++;
        }
      } catch {}
    });

    return Object.keys(hoursMap).map((h) => {
      const hr = parseInt(h, 10);
      const label = hr >= 12 ? `${hr === 12 ? 12 : hr - 12} PM` : `${hr} AM`;
      return {
        hour: label,
        appointments: hoursMap[hr],
      };
    });
  }, [appointments]);

  // High-level KPI metrics
  const totalAppointments = appointments.length;
  const bookedAppointments = appointments.filter((a) => a.status === "BOOKED").length;
  const cancelledAppointments = appointments.filter((a) => a.status === "CANCELLED").length;
  const bookingRate = totalAppointments > 0 ? Math.round((bookedAppointments / totalAppointments) * 100) : 0;
  const aiCallsTotal = totalCalls;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-primary" />
            Hospital Analytics &amp; Reports
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time appointment distributions, doctor workload breakdown, and patient booking trends.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            className="gap-1.5 cursor-pointer text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Date Filter Bar */}
      {truncated && (
        <div className="p-3 rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300 text-xs">
          Showing the first {appointments.length} appointments in this window. Narrow the date
          range for complete figures.
        </div>
      )}

      <Card className="p-4 space-y-3 bg-card border-border">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-muted-foreground flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" />
              Time Window:
            </span>
            <button
              type="button"
              onClick={() => handlePresetChange("next30")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                dateRangePreset === "next30"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Next 30 Days
            </button>
            <button
              type="button"
              onClick={() => handlePresetChange("7days")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                dateRangePreset === "7days"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Last 7 Days
            </button>
            <button
              type="button"
              onClick={() => handlePresetChange("30days")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                dateRangePreset === "30days"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Last 30 Days
            </button>
            <button
              type="button"
              onClick={() => handlePresetChange("all")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                dateRangePreset === "all"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              All Time
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">From:</span>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setDateRangePreset("custom");
              }}
              className="h-8 w-34 text-xs"
            />
            <span className="text-muted-foreground">To:</span>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setDateRangePreset("custom");
              }}
              className="h-8 w-34 text-xs"
            />
          </div>
        </div>
      </Card>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 space-y-1 bg-card border-border">
          <span className="text-xs text-muted-foreground font-medium block">Total Bookings</span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold text-foreground">{totalAppointments}</span>
            <Activity className="w-5 h-5 text-primary opacity-80" />
          </div>
          <span className="text-[11px] text-muted-foreground block">in selected period</span>
        </Card>

        <Card className="p-4 space-y-1 bg-emerald-500/10 border-emerald-500/20">
          <span className="text-xs text-emerald-800 dark:text-emerald-300 font-medium block">
            Confirmed Bookings
          </span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">
              {bookedAppointments}
            </span>
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          </div>
          <span className="text-[11px] text-emerald-700 dark:text-emerald-400 block">
            {bookingRate}% confirmation rate
          </span>
        </Card>

        <Card className="p-4 space-y-1 bg-destructive/10 border-destructive/20">
          <span className="text-xs text-destructive font-medium block">Cancellations</span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold text-destructive">{cancelledAppointments}</span>
            <Ban className="w-5 h-5 text-destructive" />
          </div>
          <span className="text-[11px] text-destructive block">
            {totalAppointments > 0
              ? `${Math.round((cancelledAppointments / totalAppointments) * 100)}% cancel rate`
              : "0%"}
          </span>
        </Card>

        <Card className="p-4 space-y-1 bg-purple-500/10 border-purple-500/20">
          <span className="text-xs text-purple-800 dark:text-purple-300 font-medium block">
            AI Telephony Volume
          </span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold text-purple-700 dark:text-purple-400">
              {aiCallsTotal}
            </span>
            <Bot className="w-5 h-5 text-purple-600" />
          </div>
          <span className="text-[11px] text-purple-700 dark:text-purple-400 block">
            calls handled by AI
          </span>
        </Card>
      </div>

      {/* Grid of Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Chart 1: Appointments per Day of Week */}
        <Card className="p-5 border-border bg-card space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border/70">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">
                Bookings by Day of Week
              </h3>
            </div>
            <Badge variant="outline" className="text-[10px]">
              Mon–Sun
            </Badge>
          </div>

          <div className="h-64 w-full text-xs">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dayOfWeekData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    borderColor: "hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="appointments" fill="var(--color-primary, #2563eb)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Chart 2: Appointment Status Breakdown Pie */}
        <Card className="p-5 border-border bg-card space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border/70">
            <div className="flex items-center gap-2">
              <PieChartIcon className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">
                Appointment Status Breakdown
              </h3>
            </div>
            <Badge variant="outline" className="text-[10px]">
              Distribution
            </Badge>
          </div>

          <div className="h-64 w-full text-xs flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {statusPieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    borderColor: "hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "11px" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Chart 3: Top 5 Doctors by Total Bookings */}
        <Card className="p-5 border-border bg-card space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border/70">
            <div className="flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">
                Top Booked Doctors
              </h3>
            </div>
            <Badge variant="outline" className="text-[10px]">
              By Volume
            </Badge>
          </div>

          <div className="h-64 w-full text-xs">
            {topDoctorsData.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <AlertCircle className="w-6 h-6 mb-1" />
                <span>No doctor booking data available for this range</span>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  layout="vertical"
                  data={topDoctorsData}
                  margin={{ top: 10, right: 20, left: 30, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      borderColor: "hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="bookings" fill="#10b981" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Chart 4: Peak Booking Hours Distribution */}
        <Card className="p-5 border-border bg-card space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border/70">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">
                Peak OPD Booking Hours
              </h3>
            </div>
            <Badge variant="outline" className="text-[10px]">
              Daily Pattern
            </Badge>
          </div>

          <div className="h-64 w-full text-xs">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hourlyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    borderColor: "hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="appointments"
                  stroke="#8b5cf6"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "#8b5cf6" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}
