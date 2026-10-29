"use client";

import * as React from "react";
import Link from "next/link";
import { listCalls, type CallSessionOut, type CallOutcome } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { toast } from "sonner";
import {
  PhoneCall,
  Clock,
  User,
  Radio,
  Filter,
  RefreshCw,
  Search,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Bot,
  MessageSquare,
  CheckCircle2,
  Info,
  Ban,
  Wrench,
  Globe2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

const OUTCOME_CONFIG: Record<
  CallOutcome,
  { label: string; badgeClass: string; icon: React.ElementType }
> = {
  BOOKED: {
    label: "Booked",
    badgeClass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    icon: CheckCircle2,
  },
  INFO_PROVIDED: {
    label: "Info Provided",
    badgeClass: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30",
    icon: Info,
  },
  ESCALATED: {
    label: "Escalated",
    badgeClass: "bg-destructive/15 text-destructive border-destructive/30 animate-pulse",
    icon: AlertTriangle,
  },
  CANCELLED: {
    label: "Cancelled",
    badgeClass: "bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30",
    icon: Ban,
  },
  RESCHEDULED: {
    label: "Rescheduled",
    badgeClass: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
    icon: RefreshCw,
  },
  ABANDONED: {
    label: "Abandoned",
    badgeClass: "bg-muted text-muted-foreground border-border",
    icon: PhoneCall,
  },
  OTHER: {
    label: "Other",
    badgeClass: "bg-muted text-muted-foreground border-border",
    icon: MessageSquare,
  },
};

export default function CallLogsPage() {
  const { hospitalId } = useHospital();

  const [calls, setCalls] = React.useState<CallSessionOut[]>([]);
  const [totalCount, setTotalCount] = React.useState(0);
  const [isLoading, setIsLoading] = React.useState(true);

  // Filters
  const [selectedOutcome, setSelectedOutcome] = React.useState<string>("");
  const [escalatedOnly, setEscalatedOnly] = React.useState(false);
  const [phoneSearch, setPhoneSearch] = React.useState("");

  // Pagination
  const [pageIndex, setPageIndex] = React.useState(0);
  const pageSize = 15;

  const fetchCalls = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Parameters<typeof listCalls>[0] = {
        limit: pageSize,
        offset: pageIndex * pageSize,
      };

      if (hospitalId) params.hospital_id = hospitalId;
      if (selectedOutcome) params.outcome = selectedOutcome as CallOutcome;
      if (escalatedOnly) params.escalated = true;
      if (phoneSearch.trim()) params.caller_phone = phoneSearch.trim();

      const res = await listCalls(params);
      setCalls(res.items);
      setTotalCount(res.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load call sessions";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, selectedOutcome, escalatedOnly, phoneSearch, pageIndex]);

  React.useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  const handleFilterChange = <T,>(setter: (val: T) => void, val: T) => {
    setter(val);
    setPageIndex(0);
  };

  const handleClearFilters = () => {
    setSelectedOutcome("");
    setEscalatedOnly(false);
    setPhoneSearch("");
    setPageIndex(0);
  };

  // Mask caller phone to protect privacy (showing last 4 digits)
  const formatPhoneMasked = (phoneStr: string) => {
    if (!phoneStr || phoneStr.length < 8) return phoneStr;
    const last4 = phoneStr.slice(-4);
    const prefix = phoneStr.slice(0, 3);
    return `${prefix} •••• ${last4}`;
  };

  // Format call duration from start and end timestamps
  const formatDuration = (startStr: string, endStr: string | null) => {
    if (!endStr) return "Active / In-progress";
    try {
      const start = new Date(startStr).getTime();
      const end = new Date(endStr).getTime();
      const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
      const mins = Math.floor(totalSeconds / 60);
      const secs = totalSeconds % 60;
      if (mins === 0) return `${secs}s`;
      return `${mins}m ${secs}s`;
    } catch {
      return "—";
    }
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

  // Summary counts
  const bookedCount = calls.filter((c) => c.call_outcome === "BOOKED").length;
  const escalatedCount = calls.filter((c) => c.escalated_to_human).length;
  const infoCount = calls.filter((c) => c.call_outcome === "INFO_PROVIDED").length;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <PhoneCall className="w-6 h-6 text-primary" />
            AI Telephony Call Logs
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Review live and past AI receptionist conversations, audio transcripts, tool executions, and caller outcomes.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-semibold">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            <span>VoIP Live Gateway</span>
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchCalls()}
            className="gap-1.5 cursor-pointer text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Mini Stats Overview Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-card border border-border rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-muted-foreground block font-medium">Total Sessions</span>
            <span className="text-xl font-bold text-foreground">{totalCount}</span>
          </div>
          <PhoneCall className="w-5 h-5 text-muted-foreground opacity-60" />
        </div>

        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-emerald-700 dark:text-emerald-400 block font-medium">Booked Appointments</span>
            <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{bookedCount}</span>
          </div>
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
        </div>

        <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-blue-700 dark:text-blue-400 block font-medium">Info Inquiries</span>
            <span className="text-xl font-bold text-blue-700 dark:text-blue-400">{infoCount}</span>
          </div>
          <Info className="w-5 h-5 text-blue-600" />
        </div>

        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <div>
            <span className="text-[11px] text-destructive block font-medium">Escalated to Staff</span>
            <span className="text-xl font-bold text-destructive">{escalatedCount}</span>
          </div>
          <AlertTriangle className="w-5 h-5 text-destructive" />
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-4 space-y-3 bg-card border-border">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Outcome Filter */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-muted-foreground">
              Filter by Call Outcome
            </label>
            <select
              value={selectedOutcome}
              onChange={(e) => handleFilterChange(setSelectedOutcome, e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">All Call Outcomes</option>
              <option value="BOOKED">Booked</option>
              <option value="INFO_PROVIDED">Info Provided</option>
              <option value="ESCALATED">Escalated</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="RESCHEDULED">Rescheduled</option>
              <option value="ABANDONED">Abandoned</option>
            </select>
          </div>

          {/* Caller Phone Filter */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-muted-foreground">
              Caller Phone Search
            </label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search phone (+91...)"
                value={phoneSearch}
                onChange={(e) => handleFilterChange(setPhoneSearch, e.target.value)}
                className="pl-9 h-9 text-xs"
              />
            </div>
          </div>

          {/* Escalation Toggle & Reset */}
          <div className="flex items-end justify-between gap-2 pb-0.5">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground py-2">
              <input
                type="checkbox"
                checked={escalatedOnly}
                onChange={(e) => handleFilterChange(setEscalatedOnly, e.target.checked)}
                className="rounded border-input text-destructive focus:ring-destructive w-4 h-4"
              />
              <span className="flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                Escalated Calls Only
              </span>
            </label>

            {(selectedOutcome || escalatedOnly || phoneSearch) && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleClearFilters}
                className="text-xs h-8 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                Reset Filters
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Calls Table */}
      <Card className="border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Call Date &amp; Time</TableHead>
              <TableHead>Caller Phone</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Language</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Turns</TableHead>
              <TableHead>Summary</TableHead>
              <TableHead className="text-right">Transcript</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i}>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="w-24 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-16 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                  </TableCell>
                  <TableCell><div className="w-28 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell><div className="w-16 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell><div className="w-8 h-4 rounded bg-muted animate-pulse" /></TableCell>
                  <TableCell><div className="w-20 h-5 rounded-full bg-muted animate-pulse" /></TableCell>
                  <TableCell><div className="w-14 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell><div className="w-36 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell className="text-right"><div className="w-20 h-7 rounded bg-muted animate-pulse ml-auto" /></TableCell>
                </TableRow>
              ))
            ) : calls.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-36 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                    <PhoneCall className="w-8 h-8 text-muted-foreground/50" />
                    <span className="text-sm font-semibold text-foreground">No call sessions found</span>
                    <p className="text-xs text-muted-foreground">
                      No telephony sessions match the current search filters.
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleClearFilters}
                      className="text-xs cursor-pointer mt-2"
                    >
                      Clear Filters
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              calls.map((call) => {
                const outcome = call.call_outcome || "OTHER";
                const meta = OUTCOME_CONFIG[outcome] || OUTCOME_CONFIG.OTHER;
                const OutcomeIcon = meta.icon;

                return (
                  <TableRow key={call.id} className="hover:bg-muted/40 transition-colors">
                    {/* Timestamp */}
                    <TableCell>
                      <div className="space-y-0.5">
                        <span className="font-semibold text-foreground text-xs block">
                          {formatDateTime(call.call_start)}
                        </span>
                        <span className="text-[10px] font-mono text-muted-foreground block truncate max-w-[120px]">
                          {call.id.slice(0, 8)}...
                        </span>
                      </div>
                    </TableCell>

                    {/* Caller Phone */}
                    <TableCell>
                      <div className="flex items-center gap-1.5 font-medium text-xs text-foreground">
                        <User className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span>{formatPhoneMasked(call.caller_phone)}</span>
                      </div>
                    </TableCell>

                    {/* Duration */}
                    <TableCell>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3 text-muted-foreground shrink-0" />
                        <span>{formatDuration(call.call_start, call.call_end)}</span>
                      </div>
                    </TableCell>

                    {/* Language */}
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] font-mono uppercase">
                        <Globe2 className="w-2.5 h-2.5 mr-1" />
                        {call.language_detected || "en"}
                      </Badge>
                    </TableCell>

                    {/* Outcome Badge */}
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Badge
                          variant="outline"
                          className={`gap-1 text-[11px] font-medium ${meta.badgeClass}`}
                        >
                          <OutcomeIcon className="w-3 h-3" />
                          {meta.label}
                        </Badge>

                        {call.escalated_to_human && (
                          <span
                            title="Escalated to human staff"
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30"
                          >
                            ⚠️ ER
                          </span>
                        )}
                      </div>
                    </TableCell>

                    {/* Turns */}
                    <TableCell>
                      <span className="text-xs font-semibold text-foreground">
                        {call.total_turns} turns
                      </span>
                    </TableCell>

                    {/* Summary snippet */}
                    <TableCell>
                      <p className="text-xs text-muted-foreground max-w-[260px] truncate" title={call.summary || ""}>
                        {call.summary || "No summary recorded"}
                      </p>
                    </TableCell>

                    {/* Action */}
                    <TableCell className="text-right">
                      <Link
                        href={`/call-logs/${call.id}`}
                        className="inline-flex items-center justify-center h-8 px-2.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-muted text-foreground transition-colors cursor-pointer gap-1"
                      >
                        <MessageSquare className="w-3 h-3 text-primary" />
                        <span>Transcript</span>
                        <ExternalLink className="w-3 h-3 text-muted-foreground" />
                      </Link>
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
            of <span className="font-semibold text-foreground">{totalCount}</span> sessions
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
    </div>
  );
}
