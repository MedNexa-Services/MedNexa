"use client";

import * as React from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { toast } from "sonner";
import { listCalls, type CallOutcome, type CallSessionOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { LANGUAGES, formatDateTime, formatDuration } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { CALL_OUTCOME_LABELS, CallOutcomeLabel } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

export default function CallsPage() {
  const { hospitalId } = useHospital();
  const [calls, setCalls] = React.useState<CallSessionOut[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [outcome, setOutcome] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [phoneQuery, setPhoneQuery] = React.useState("");
  const [page, setPage] = React.useState(0);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setPhoneQuery(phone.trim());
      setPage(0);
    }, 400);
    return () => clearTimeout(timer);
  }, [phone]);

  const load = React.useCallback(async () => {
    if (!hospitalId) return;
    try {
      const res = await listCalls({
        hospital_id: hospitalId,
        outcome: (outcome || undefined) as CallOutcome | undefined,
        caller_phone: phoneQuery || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setCalls(res.items);
      setTotal(res.total);
    } catch (err) {
      if (phoneQuery) {
        setCalls([]);
        setTotal(0);
      } else {
        toast.error(err instanceof Error ? err.message : "Calls could not be loaded.");
      }
    } finally {
      setLoading(false);
    }
  }, [hospitalId, outcome, phoneQuery, page]);

  React.useEffect(() => {
    load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, [load]);

  const showEscalated = () => {
    setOutcome(outcome === "ESCALATED" ? "" : "ESCALATED");
    setPage(0);
  };

  return (
    <>
      <PageHeader
        title="Calls"
        description="Every call the AI receptionist answered, with what was said and what it did."
        actions={
          <Button variant={outcome === "ESCALATED" ? "default" : "outline"} onClick={showEscalated}>
            Passed to staff
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <NativeSelect
          aria-label="Outcome"
          value={outcome}
          onChange={(e) => {
            setOutcome(e.target.value);
            setPage(0);
          }}
          className="w-52"
        >
          <option value="">Any outcome</option>
          {Object.entries(CALL_OUTCOME_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </NativeSelect>
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            inputMode="tel"
            aria-label="Caller's phone number"
            placeholder="Caller's full phone number"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="h-8 bg-card pl-8"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {loading ? (
          <div className="h-72 animate-pulse" />
        ) : calls.length === 0 ? (
          <div className="px-6 py-10">
            <p className="text-sm font-semibold">
              {outcome || phoneQuery ? "No calls match" : "No calls yet"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {outcome || phoneQuery
                ? "Try another outcome, or the caller's full 10-digit number."
                : "Calls appear here as soon as the receptionist answers them."}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Started</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead className="w-full">Summary</TableHead>
                <TableHead>Length</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {calls.map((call) => (
                <TableRow key={call.id} className={cn(call.escalated_to_human && "bg-status-moved/5")}>
                  <TableCell>
                    <Link href={`/call-logs/${call.id}`} className="font-medium hover:underline">
                      {formatDateTime(call.call_start)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {call.caller_phone}
                    {call.language_detected && (
                      <span className="block text-[13px] text-muted-foreground">
                        {LANGUAGES[call.language_detected] ?? call.language_detected}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <CallOutcomeLabel outcome={call.call_outcome} ended={call.call_end !== null} />
                  </TableCell>
                  <TableCell className="max-w-md truncate whitespace-nowrap text-muted-foreground" title={call.summary ?? ""}>
                    {call.summary ?? `${call.total_turns} turns`}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {call.call_end
                      ? formatDuration((Date.parse(call.call_end) - Date.parse(call.call_start)) / 1000)
                      : "Ongoing"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </div>
    </>
  );
}
