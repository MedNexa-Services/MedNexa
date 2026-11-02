"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { getCall, type CallLogOut, type CallSessionDetailOut } from "@/lib/api";
import { LANGUAGES, formatDateTime, formatDuration } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { BackLink, DetailList } from "@/components/detail-list";
import { CallOutcomeLabel } from "@/components/status";
import { cn } from "@/lib/utils";

function clock(timestamp: string): string {
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true })
    .format(new Date(timestamp))
    .replace(/am|pm/, (s) => s.toUpperCase());
}

function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function Turn({ log }: { log: CallLogOut }) {
  const time = (
    <time className="tabular pt-0.5 text-[13px] text-muted-foreground" dateTime={log.timestamp}>
      {clock(log.timestamp)}
    </time>
  );
  if (log.role === "TOOL" || log.role === "SYSTEM") {
    return (
      <li className="grid grid-cols-[6.5rem_1fr] gap-3 px-4 py-1.5 text-[13px] text-muted-foreground">
        {time}
        <details>
          <summary className="cursor-pointer select-none">
            {log.role === "TOOL" ? `Looked up: ${log.tool_called ?? "a tool"}` : log.content}
            {log.appointment_id && (
              <>
                {" "}
                <Link href={`/appointments/${log.appointment_id}`} className="text-foreground underline">
                  open appointment
                </Link>
              </>
            )}
          </summary>
          {log.role === "TOOL" && (
            <div className="mt-2 space-y-2">
              {log.content && <p>{log.content}</p>}
              {log.tool_result && (
                <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-2 font-mono text-xs whitespace-pre-wrap">
                  {prettyJson(log.tool_result)}
                </pre>
              )}
            </div>
          )}
        </details>
      </li>
    );
  }
  const caller = log.role === "USER";
  return (
    <li className="grid grid-cols-[6.5rem_1fr] gap-3 px-4 py-2.5">
      {time}
      <div>
        <p className={cn("text-[13px] font-medium", caller ? "text-foreground" : "text-primary")}>
          {caller ? "Caller" : "Receptionist"}
        </p>
        <p className="max-w-[70ch] text-sm whitespace-pre-wrap">{log.content}</p>
      </div>
    </li>
  );
}

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = React.useState<CallSessionDetailOut | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    try {
      setCall(await getCall(id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "The call could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  React.useEffect(() => {
    load();
  }, [load]);

  React.useEffect(() => {
    if (!call || call.call_end) return;
    const timer = setInterval(load, 5_000);
    return () => clearInterval(timer);
  }, [call, load]);

  const back = <BackLink href="/call-logs">Calls</BackLink>;
  if (loading) return <div className="h-80 animate-pulse rounded-lg border border-border bg-card" />;
  if (!call) {
    return (
      <>
        <PageHeader back={back} title="Call not found" />
        <p className="text-sm text-muted-foreground">
          Calls are deleted automatically after the retention period, or the link may be wrong.
        </p>
      </>
    );
  }

  const appointmentIds = [...new Set(call.logs.map((l) => l.appointment_id).filter(Boolean))] as string[];
  const ended = call.call_end !== null;

  return (
    <>
      <PageHeader back={back} title={`Call from ${call.caller_phone}`} description={formatDateTime(call.call_start)} />

      {call.escalated_to_human && (
        <div role="note" className="mb-6 rounded-lg border border-status-moved/40 bg-card px-4 py-3 text-sm">
          <p className="font-medium">The receptionist passed this caller to staff.</p>
          <p className="text-muted-foreground">
            If they weren&apos;t connected, call them back on {call.caller_phone}.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <section className="self-start rounded-lg border border-border bg-card">
          <DetailList
            items={[
              { label: "Outcome", value: <CallOutcomeLabel outcome={call.call_outcome} ended={ended} /> },
              { label: "Summary", value: call.summary },
              {
                label: "Length",
                value: ended
                  ? formatDuration((Date.parse(call.call_end!) - Date.parse(call.call_start)) / 1000)
                  : "Still on the line",
              },
              {
                label: "Language",
                value: call.language_detected && (LANGUAGES[call.language_detected] ?? call.language_detected),
              },
              { label: "Turns", value: call.total_turns },
              {
                label: appointmentIds.length > 1 ? "Appointments" : "Appointment",
                value: appointmentIds.length > 0 && (
                  <span className="flex flex-col">
                    {appointmentIds.map((appointmentId, i) => (
                      <Link key={appointmentId} href={`/appointments/${appointmentId}`} className="underline">
                        {appointmentIds.length > 1 ? `Appointment ${i + 1}` : "Open the appointment"}
                      </Link>
                    ))}
                  </span>
                ),
              },
            ]}
          />
        </section>

        <section className="rounded-lg border border-border bg-card">
          <h2 className="border-b border-border px-4 py-3 text-[15px] font-semibold">Transcript</h2>
          {call.logs.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">Nothing was said on this call.</p>
          ) : (
            <ol className="py-2">
              {call.logs.map((log) => (
                <Turn key={log.id} log={log} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}
