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
  rescheduleAppointment,
  getDoctorSlots,
  type AppointmentOut,
  type SlotOut,
} from "@/lib/api";
import { toast } from "sonner";
import { Calendar, Clock, RefreshCw, Loader2, AlertCircle } from "lucide-react";

interface RescheduleAppointmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointment: AppointmentOut | null;
  onSuccess: () => void;
}

export function RescheduleAppointmentDialog({
  open,
  onOpenChange,
  appointment,
  onSuccess,
}: RescheduleAppointmentDialogProps) {
  const [newDate, setNewDate] = React.useState("");
  const [newSlot, setNewSlot] = React.useState("");
  const [slots, setSlots] = React.useState<SlotOut[]>([]);
  const [loadingSlots, setLoadingSlots] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open && appointment) {
      setNewDate(appointment.appointment_date);
      setNewSlot("");
    }
  }, [open, appointment]);

  React.useEffect(() => {
    if (!open || !appointment || !newDate) return;

    let isCancelled = false;
    async function fetchSlots() {
      if (!appointment) return;
      setLoadingSlots(true);
      setNewSlot("");
      try {
        const availableSlots = await getDoctorSlots(appointment.doctor_id, newDate);
        if (!isCancelled) {
          setSlots(availableSlots);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          setSlots([]);
        }
      } finally {
        if (!isCancelled) {
          setLoadingSlots(false);
        }
      }
    }

    fetchSlots();
    return () => {
      isCancelled = true;
    };
  }, [open, appointment, newDate]);

  if (!appointment) return null;

  const formatSlotTime = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  const handleReschedule = async () => {
    if (!newDate || !newSlot) {
      toast.error("Please pick a new date and time slot.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await rescheduleAppointment(appointment.id, {
        new_date: newDate,
        new_time: newSlot,
      });

      toast.success(
        `Appointment rescheduled! New Token #${res.token_number} on ${res.appointment_date} at ${formatSlotTime(
          res.appointment_time
        )}`
      );
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to reschedule appointment";
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
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 flex items-center justify-center">
              <RefreshCw className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold">Reschedule Appointment</DialogTitle>
              <DialogDescription className="text-xs">
                Select a new appointment date and time for {appointment.patient_name}.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Current Appointment Banner */}
          <div className="p-3 bg-muted/40 rounded-lg border border-border text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Current Schedule:</span>
              <span className="font-semibold text-foreground">
                {appointment.appointment_date} at {formatSlotTime(appointment.appointment_time)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Doctor:</span>
              <span className="font-semibold text-foreground">{appointment.doctor_name}</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reschedule-date" className="text-xs font-semibold flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
              New Appointment Date <span className="text-destructive">*</span>
            </Label>
            <Input
              id="reschedule-date"
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              required
            />
          </div>

          {/* New Slot Picker */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                Select New Slot <span className="text-destructive">*</span>
              </span>
              <span className="text-muted-foreground text-[11px] font-normal">
                {slots.length} available
              </span>
            </Label>

            {loadingSlots ? (
              <div className="flex items-center justify-center p-6 text-xs text-muted-foreground gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span>Loading open slots...</span>
              </div>
            ) : slots.length === 0 ? (
              <div className="text-center p-4 border border-dashed border-border rounded-lg text-muted-foreground space-y-1">
                <AlertCircle className="w-5 h-5 mx-auto text-amber-500" />
                <p className="text-xs font-medium text-foreground">No available slots for this date</p>
                <p className="text-[11px]">Please select another date on the doctor&apos;s working calendar.</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2 max-h-40 overflow-y-auto p-1">
                {slots.map((slot) => {
                  const isSelected = newSlot === slot.start;
                  return (
                    <button
                      key={slot.start}
                      type="button"
                      onClick={() => setNewSlot(slot.start)}
                      className={`px-2 py-1.5 text-xs font-medium rounded-md border text-center transition-all cursor-pointer ${
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary ring-2 ring-primary/30"
                          : "bg-card border-border hover:bg-muted text-foreground"
                      }`}
                    >
                      {formatSlotTime(slot.start)}
                    </button>
                  );
                })}
              </div>
            )}
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
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleReschedule}
            disabled={!newDate || !newSlot || isSubmitting}
            className="gap-1.5 cursor-pointer bg-amber-600 hover:bg-amber-700 text-white"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Rescheduling...</span>
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                <span>Confirm Reschedule</span>
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
