"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getCall, type CallSessionDetailOut, type CallOutcome, type CallRole } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft,
  PhoneCall,
  Clock,
  User,
  Bot,
  Wrench,
  Globe2,
  CheckCircle2,
  AlertTriangle,
  Info,
  Ban,
  RefreshCw,
  ExternalLink,
  CalendarCheck2,
  FileText,
  Loader2,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

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
    icon: PhoneCall,
  },
};

export default function CallTranscriptPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = Array.isArray(params.id) ? params.id[0] : (params.id as string);

  const [call, setCall] = React.useState<CallSessionDetailOut | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  const fetchCall = React.useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const data = await getCall(sessionId);
      setCall(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load call transcript";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  React.useEffect(() => {
    fetchCall();
  }, [fetchCall]);

  const formatDuration = (startStr: string, endStr: string | null) => {
    if (!endStr) return "Active / In-progress";
    try {
      const start = new Date(startStr).getTime();
      const end = new Date(endStr).getTime();
      const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
      const mins = Math.floor(totalSeconds / 60);
      const secs = totalSeconds % 60;
      if (mins === 0) return `${secs} seconds`;
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
        second: "numeric",
        hour12: true,
      });
    } catch {
      return isoStr;
    }
  };

  const formatTimeOnly = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "numeric",
        second: "numeric",
        hour12: true,
      });
    } catch {
      return "";
    }
  };

  // Find any booked appointment linked to this call
  const bookedAppointmentId = React.useMemo(() => {
    if (!call?.logs) return null;
    const logWithApt = call.logs.find((l) => l.appointment_id);
    return logWithApt ? logWithApt.appointment_id : null;
  }, [call]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading call transcript...</p>
      </div>
    );
  }

  if (!call) {
    return (
      <div className="space-y-4">
        <Link
          href="/call-logs"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Call Logs</span>
        </Link>
        <Card className="p-8 text-center border-dashed border-border">
          <AlertTriangle className="w-8 h-8 mx-auto text-amber-500 mb-2" />
          <h3 className="text-base font-semibold">Call Session Not Found</h3>
          <Button size="sm" onClick={() => router.push("/call-logs")} className="mt-4">
            Return to Call Logs
          </Button>
        </Card>
      </div>
    );
  }

  const outcome = call.call_outcome || "OTHER";
  const meta = OUTCOME_CONFIG[outcome] || OUTCOME_CONFIG.OTHER;
  const OutcomeIcon = meta.icon;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/call-logs"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Call Logs</span>
        </Link>

        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={`gap-1 text-xs font-semibold px-2.5 py-1 ${meta.badgeClass}`}
          >
            <OutcomeIcon className="w-3.5 h-3.5" />
            {meta.label}
          </Badge>

          <Badge variant="outline" className="text-xs uppercase font-mono">
            <Globe2 className="w-3 h-3 mr-1" />
            {call.language_detected || "en"}
          </Badge>
        </div>
      </div>

      {/* Escalation Warning Banner */}
      {call.escalated_to_human && (
        <div className="p-4 rounded-xl border border-destructive/40 bg-destructive/10 text-destructive flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-destructive/20 text-destructive flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Escalated to Human Emergency Staff</h3>
              <p className="text-xs opacity-90">
                The AI receptionist flagged this caller for urgent human clinical intervention.
              </p>
            </div>
          </div>
          <Badge variant="destructive" className="text-xs font-bold uppercase tracking-wider">
            Critical Escalation
          </Badge>
        </div>
      )}

      {/* Linked Appointment Banner */}
      {bookedAppointmentId && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/20 text-emerald-600 flex items-center justify-center shrink-0">
              <CalendarCheck2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Appointment Booked During This Call</h3>
              <p className="text-xs opacity-90">
                A consultation slot was verified and confirmed in hospital records.
              </p>
            </div>
          </div>

          <Link
            href={`/appointments/${bookedAppointmentId}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors cursor-pointer"
          >
            <span>View Appointment</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Call Metadata Card */}
      <Card className="p-5 border-border bg-card space-y-4">
        <div className="flex items-center gap-3 pb-3 border-b border-border/70">
          <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
            <PhoneCall className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">
              Call with {call.caller_phone}
            </h1>
            <p className="text-xs text-muted-foreground">
              Session ID: <code className="font-mono">{call.id}</code>
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="space-y-0.5">
            <span className="text-muted-foreground block font-medium">Started At</span>
            <span className="font-semibold text-foreground block">
              {formatDateTime(call.call_start)}
            </span>
          </div>

          <div className="space-y-0.5">
            <span className="text-muted-foreground block font-medium">Call Duration</span>
            <span className="font-semibold text-foreground flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              {formatDuration(call.call_start, call.call_end)}
            </span>
          </div>

          <div className="space-y-0.5">
            <span className="text-muted-foreground block font-medium">Total Turns</span>
            <span className="font-semibold text-foreground block">
              {call.total_turns} conversation turns
            </span>
          </div>

          <div className="space-y-0.5">
            <span className="text-muted-foreground block font-medium">Outcome</span>
            <span className="font-semibold text-foreground block">{meta.label}</span>
          </div>
        </div>

        {call.summary && (
          <div className="pt-2 border-t border-border/60">
            <span className="text-xs font-bold text-muted-foreground block uppercase tracking-wider mb-1 flex items-center gap-1">
              <FileText className="w-3 h-3" />
              AI Session Summary
            </span>
            <p className="text-xs text-foreground leading-relaxed p-3 bg-muted/40 rounded-lg border border-border/50">
              {call.summary}
            </p>
          </div>
        )}
      </Card>

      {/* Turn-by-Turn Dialogue Transcript View */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" />
            Turn-by-Turn Dialogue Transcript ({call.logs.length} entries)
          </h2>
          <span className="text-xs text-muted-foreground">Chronological Order</span>
        </div>

        <div className="space-y-3.5">
          {call.logs.map((log) => {
            const isCaller = log.role === "USER";
            const isAssistant = log.role === "ASSISTANT";
            const isTool = log.role === "TOOL";
            const isSystem = log.role === "SYSTEM";

            // Tool Execution Entry
            if (isTool) {
              let parsedResult = null;
              try {
                if (log.tool_result) {
                  parsedResult = JSON.parse(log.tool_result);
                }
              } catch {
                parsedResult = log.tool_result;
              }

              return (
                <div
                  key={log.id}
                  className="p-3 rounded-lg border border-dashed border-border bg-muted/20 text-xs space-y-2 max-w-2xl mx-auto"
                >
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="font-mono font-bold text-[11px] text-primary flex items-center gap-1.5">
                      <Wrench className="w-3.5 h-3.5" />
                      Tool Invocated: <code>{log.tool_called || "system_tool"}</code>
                    </span>
                    <span className="text-[10px]">{formatTimeOnly(log.timestamp)}</span>
                  </div>

                  <p className="text-foreground text-[11px] italic">{log.content}</p>

                  {log.tool_result && (
                    <div className="p-2 rounded bg-background border border-border/60 font-mono text-[10px] text-muted-foreground overflow-x-auto">
                      <pre className="whitespace-pre-wrap">
                        {typeof parsedResult === "object"
                          ? JSON.stringify(parsedResult, null, 2)
                          : log.tool_result}
                      </pre>
                    </div>
                  )}

                  {log.appointment_id && (
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[10px] text-muted-foreground">
                        Linked Appointment: <code className="font-mono">{log.appointment_id}</code>
                      </span>
                      <Link
                        href={`/appointments/${log.appointment_id}`}
                        className="text-[10px] text-primary hover:underline flex items-center gap-1"
                      >
                        <span>View</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </Link>
                    </div>
                  )}
                </div>
              );
            }

            // System Entry
            if (isSystem) {
              return (
                <div key={log.id} className="text-center py-1">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                    {log.content} • {formatTimeOnly(log.timestamp)}
                  </span>
                </div>
              );
            }

            // Caller vs AI Speech Bubbles
            return (
              <div
                key={log.id}
                className={`flex items-start gap-2.5 ${
                  isCaller ? "justify-end" : "justify-start"
                }`}
              >
                {!isCaller && (
                  <div className="w-8 h-8 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[80%] sm:max-w-[70%] rounded-2xl p-3.5 text-xs shadow-xs space-y-1 ${
                    isCaller
                      ? "bg-primary text-primary-foreground rounded-tr-xs"
                      : "bg-card border border-border text-foreground rounded-tl-xs"
                  }`}
                >
                  <div
                    className={`flex items-center justify-between gap-3 text-[10px] font-semibold ${
                      isCaller ? "text-primary-foreground/75" : "text-muted-foreground"
                    }`}
                  >
                    <span>{isCaller ? "Caller" : "MedNexa AI"}</span>
                    <span>{formatTimeOnly(log.timestamp)}</span>
                  </div>

                  <p className="text-xs leading-relaxed whitespace-pre-wrap">{log.content}</p>
                </div>

                {isCaller && (
                  <div className="w-8 h-8 rounded-full bg-muted text-muted-foreground flex items-center justify-center shrink-0 border border-border">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
