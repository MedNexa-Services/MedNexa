"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  upsertScheduleOverride,
  deleteScheduleOverride,
  type ScheduleOverrideOut,
} from "@/lib/api";
import { toast } from "sonner";
import { useHospital } from "@/contexts/HospitalContext";
import { todayIn } from "@/lib/dates";
import { Calendar, Clock, Ban, Trash2, Save, Loader2, Sparkles } from "lucide-react";

interface ScheduleOverrideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  doctorId: string;
  doctorName: string;
  defaultDate?: string;
  existingOverride?: ScheduleOverrideOut | null;
  onSuccess: () => void;
}

export function ScheduleOverrideDialog({
  open,
  onOpenChange,
  doctorId,
  doctorName,
  defaultDate,
  existingOverride,
  onSuccess,
}: ScheduleOverrideDialogProps) {
  const { hospital } = useHospital();
  const today = todayIn(hospital?.timezone);
  const [date, setDate] = React.useState(defaultDate || today);
  const [isLeave, setIsLeave] = React.useState(true); // true = Leave/Unavailable, false = Custom hours
  const [startTime, setStartTime] = React.useState("09:00");
  const [endTime, setEndTime] = React.useState("17:00");
  const [reason, setReason] = React.useState("");

  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      if (existingOverride) {
        setDate(existingOverride.date);
        setIsLeave(!existingOverride.is_available);
        setStartTime(
          existingOverride.start_time ? existingOverride.start_time.slice(0, 5) : "09:00"
        );
        setEndTime(existingOverride.end_time ? existingOverride.end_time.slice(0, 5) : "17:00");
        setReason(existingOverride.override_reason || "");
      } else {
        setDate(defaultDate || today);
        setIsLeave(true);
        setStartTime("09:00");
        setEndTime("17:00");
        setReason("");
      }
    }
  }, [open, defaultDate, existingOverride, today]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!date) {
      toast.error("Please pick a date for the override.");
      return;
    }

    if (!isLeave && endTime <= startTime) {
      toast.error("Shift end time must be after start time.");
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        date,
        is_available: !isLeave,
        start_time: isLeave ? null : `${startTime}:00`,
        end_time: isLeave ? null : `${endTime}:00`,
        override_reason: reason.trim() || (isLeave ? "Doctor on leave" : "Custom working hours"),
      };

      await upsertScheduleOverride(doctorId, payload);
      toast.success(
        isLeave
          ? `Leave recorded for ${doctorName} on ${date}`
          : `Custom shift scheduled for ${doctorName} on ${date}`
      );
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save schedule override";
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!existingOverride && !date) return;
    const targetDate = existingOverride?.date || date;

    setIsDeleting(true);
    try {
      await deleteScheduleOverride(doctorId, targetDate);
      toast.success(`Removed override for ${targetDate}. Doctor reverts to weekly template.`);
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete schedule override";
      toast.error(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSave}>
          <DialogHeader>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <Calendar className="w-4 h-4" />
              </div>
              <div>
                <DialogTitle className="text-base font-bold">
                  {existingOverride ? "Edit Schedule Override" : "Add Schedule Override"}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Configure special leave dates or modified working hours for {doctorName}.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-4 py-3">
            {/* Target Date */}
            <div className="space-y-1.5">
              <Label htmlFor="override-date" className="text-xs font-semibold flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                Target Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="override-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </div>

            {/* Override Mode: Leave vs Custom Hours */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Override Type</Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setIsLeave(true)}
                  className={`flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-semibold cursor-pointer transition-all ${
                    isLeave
                      ? "border-destructive bg-destructive/10 text-destructive ring-1 ring-destructive"
                      : "border-border bg-card hover:bg-muted text-muted-foreground"
                  }`}
                >
                  <Ban className="w-4 h-4" />
                  <span>On Leave / Closed</span>
                </button>

                <button
                  type="button"
                  onClick={() => setIsLeave(false)}
                  className={`flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-semibold cursor-pointer transition-all ${
                    !isLeave
                      ? "border-primary bg-primary/10 text-primary ring-1 ring-primary"
                      : "border-border bg-card hover:bg-muted text-muted-foreground"
                  }`}
                >
                  <Clock className="w-4 h-4" />
                  <span>Custom Shift Hours</span>
                </button>
              </div>
            </div>

            {/* Custom Hours (if not leave) */}
            {!isLeave && (
              <div className="grid grid-cols-2 gap-3 p-3 bg-muted/30 border border-border rounded-lg">
                <div className="space-y-1.5">
                  <Label htmlFor="override-start-time" className="text-xs font-semibold">
                    Shift Start Time
                  </Label>
                  <Input
                    id="override-start-time"
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    required={!isLeave}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="override-end-time" className="text-xs font-semibold">
                    Shift End Time
                  </Label>
                  <Input
                    id="override-end-time"
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    required={!isLeave}
                  />
                </div>
              </div>
            )}

            {/* Reason */}
            <div className="space-y-1.5">
              <Label htmlFor="override-reason" className="text-xs font-semibold">
                Reason / Note (optional)
              </Label>
              <Input
                id="override-reason"
                placeholder={
                  isLeave
                    ? "e.g. Conference, Medical leave, Diwali Holiday"
                    : "e.g. Extended evening clinic, Morning emergency rounds"
                }
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={200}
              />
            </div>
          </div>

          <DialogFooter className="flex items-center justify-between gap-2 border-t border-border pt-3">
            {existingOverride ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting || isSaving}
                className="text-xs text-destructive hover:bg-destructive/10 gap-1.5 cursor-pointer"
              >
                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                <span>Remove Override</span>
              </Button>
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="cursor-pointer text-xs"
              >
                Cancel
              </Button>
            )}

            <Button
              type="submit"
              size="sm"
              disabled={isSaving || isDeleting}
              className="gap-1.5 cursor-pointer text-xs"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Override</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
