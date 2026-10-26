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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cancelAppointment, type AppointmentOut } from "@/lib/api";
import { toast } from "sonner";
import { AlertTriangle, Loader2, Ban } from "lucide-react";

interface CancelAppointmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointment: AppointmentOut | null;
  onSuccess: () => void;
}

export function CancelAppointmentDialog({
  open,
  onOpenChange,
  appointment,
  onSuccess,
}: CancelAppointmentDialogProps) {
  const [reason, setReason] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open]);

  if (!appointment) return null;

  const handleCancel = async () => {
    setIsSubmitting(true);
    try {
      await cancelAppointment(appointment.id, {
        reason: reason.trim() || "Cancelled by hospital staff",
      });
      toast.success(`Appointment #${appointment.token_number} cancelled successfully`);
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel appointment";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-destructive/10 text-destructive flex items-center justify-center">
              <Ban className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-destructive">
                Cancel Patient Appointment
              </DialogTitle>
              <DialogDescription className="text-xs">
                This will release the reserved time slot back into available capacity.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Appointment details preview */}
          <div className="p-3 bg-muted/40 rounded-lg border border-border text-xs space-y-1.5">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Patient:</span>
              <span className="font-semibold text-foreground">{appointment.patient_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Doctor:</span>
              <span className="font-semibold text-foreground">{appointment.doctor_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Date &amp; Time:</span>
              <span className="font-semibold text-foreground">
                {appointment.appointment_date} at {appointment.appointment_time.slice(0, 5)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Token Number:</span>
              <span className="font-bold text-primary">#{appointment.token_number}</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cancel-reason" className="text-xs font-semibold">
              Reason for Cancellation (optional)
            </Label>
            <Textarea
              id="cancel-reason"
              rows={3}
              placeholder="e.g. Patient called to cancel; emergency reschedule; duplicate booking."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 p-2.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>This action cannot be undone. You will need to create a new appointment if needed.</span>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
            className="cursor-pointer"
          >
            Go Back
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="gap-1.5 cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Cancelling...</span>
              </>
            ) : (
              <>
                <Ban className="w-4 h-4" />
                <span>Confirm Cancellation</span>
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
