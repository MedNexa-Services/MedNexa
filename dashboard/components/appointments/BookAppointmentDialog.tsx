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
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  listDoctors,
  getDoctorSlots,
  bookAppointment,
  type DoctorOut,
  type SlotOut,
  type BookingConfirmation,
  type Gender,
} from "@/lib/api";
import { toast } from "sonner";
import { useHospital } from "@/contexts/HospitalContext";
import { todayIn } from "@/lib/dates";
import {
  Calendar,
  Clock,
  User,
  Phone,
  CheckCircle2,
  Stethoscope,
  ChevronRight,
  ChevronLeft,
  Loader2,
  AlertCircle,
  FileText,
  Hash,
} from "lucide-react";

interface BookAppointmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultDate?: string;
  defaultDoctorId?: string;
  onSuccess: () => void;
}

export function BookAppointmentDialog({
  open,
  onOpenChange,
  defaultDate,
  defaultDoctorId,
  onSuccess,
}: BookAppointmentDialogProps) {
  const [step, setStep] = React.useState<1 | 2 | 3 | 4>(1);

  // Doctors list
  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [loadingDoctors, setLoadingDoctors] = React.useState(false);

  // Step 1: Doctor & Slot selection
  const [selectedDoctorId, setSelectedDoctorId] = React.useState<string>(defaultDoctorId || "");
  const { hospitalId, hospital } = useHospital();
  const today = todayIn(hospital?.timezone);
  const [selectedDate, setSelectedDate] = React.useState<string>(defaultDate || today);
  const [slots, setSlots] = React.useState<SlotOut[]>([]);
  const [loadingSlots, setLoadingSlots] = React.useState(false);
  const [selectedSlot, setSelectedSlot] = React.useState<string>("");

  // Step 2: Patient Info
  const [patientName, setPatientName] = React.useState("");
  const [patientPhone, setPatientPhone] = React.useState("+91");
  const [patientAge, setPatientAge] = React.useState<string>("");
  const [patientGender, setPatientGender] = React.useState<Gender | "">("");
  const [patientEmail, setPatientEmail] = React.useState("");
  const [notes, setNotes] = React.useState("");

  // Step 4 / Submission
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [confirmation, setConfirmation] = React.useState<BookingConfirmation | null>(null);

  // Load doctors on dialog open
  React.useEffect(() => {
    if (open) {
      setStep(1);
      setConfirmation(null);
      setSelectedDoctorId(defaultDoctorId || "");
      setSelectedDate(defaultDate || today);
      setSelectedSlot("");
      setPatientName("");
      setPatientPhone("+91");
      setPatientAge("");
      setPatientGender("");
      setPatientEmail("");
      setNotes("");

      async function fetchDoctors() {
        setLoadingDoctors(true);
        try {
          const res = await listDoctors({
            hospital_id: hospitalId,
            include_inactive: false,
            limit: 100,
          });
          setDoctors(res.items);
          if (!defaultDoctorId && res.items.length > 0) {
            setSelectedDoctorId(res.items[0].id);
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "Failed to load doctors";
          toast.error(msg);
        } finally {
          setLoadingDoctors(false);
        }
      }
      fetchDoctors();
    }
  }, [open, defaultDate, defaultDoctorId, hospitalId, today]);

  // Load slots when doctor or date changes
  React.useEffect(() => {
    if (!open || !selectedDoctorId || !selectedDate) return;

    let isCancelled = false;
    async function fetchSlots() {
      setLoadingSlots(true);
      setSelectedSlot("");
      try {
        const availableSlots = await getDoctorSlots(selectedDoctorId, selectedDate);
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
  }, [open, selectedDoctorId, selectedDate]);

  const selectedDoctor = React.useMemo(() => {
    return doctors.find((d) => d.id === selectedDoctorId);
  }, [doctors, selectedDoctorId]);

  // Step navigation validations
  const canProceedStep1 = selectedDoctorId && selectedDate && selectedSlot;
  const canProceedStep2 = patientName.trim().length >= 2 && patientPhone.trim().length >= 10;

  const handleNext = () => {
    if (step === 1 && canProceedStep1) {
      setStep(2);
    } else if (step === 2 && canProceedStep2) {
      setStep(3);
    }
  };

  const handleBack = () => {
    if (step === 2) setStep(1);
    if (step === 3) setStep(2);
  };

  const handleConfirmBooking = async () => {
    if (!selectedDoctorId || !selectedDate || !selectedSlot) return;

    setIsSubmitting(true);
    try {
      const payload = {
        patient: {
          name: patientName.trim(),
          phone: patientPhone.trim(),
          age: patientAge ? parseInt(patientAge, 10) : null,
          gender: patientGender ? (patientGender as Gender) : null,
          email: patientEmail.trim() || null,
        },
        doctor_id: selectedDoctorId,
        appointment_date: selectedDate,
        appointment_time: selectedSlot,
        notes: notes.trim() || null,
        booking_source: "DASHBOARD" as const,
      };

      const result = await bookAppointment(payload);
      setConfirmation(result);
      setStep(4);
      toast.success(`Appointment confirmed! Token #${result.token_number}`);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to book appointment";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatSlotTime = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(":");
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? "PM" : "AM";
    const formattedH = h % 12 === 0 ? 12 : h % 12;
    return `${formattedH}:${minutes} ${ampm}`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
              <Calendar className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold">
                {step === 4 ? "Appointment Confirmed" : "Book New Patient Appointment"}
              </DialogTitle>
              <DialogDescription className="text-xs">
                {step === 1 && "Step 1 of 3: Select Doctor, Appointment Date & Available Slot"}
                {step === 2 && "Step 2 of 3: Enter Patient Details & Clinical Reason"}
                {step === 3 && "Step 3 of 3: Review Details & Issue Token"}
                {step === 4 && "Booking completed and confirmed in hospital records"}
              </DialogDescription>
            </div>
          </div>

          {/* Stepper progress indicator */}
          {step <= 3 && (
            <div className="flex items-center justify-between pt-4 pb-1">
              <div
                className={`flex items-center gap-1.5 text-xs font-semibold ${
                  step >= 1 ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                    step >= 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  1
                </div>
                <span>Doctor &amp; Slot</span>
              </div>
              <div className="flex-1 h-0.5 mx-2 bg-border" />
              <div
                className={`flex items-center gap-1.5 text-xs font-semibold ${
                  step >= 2 ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                    step >= 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  2
                </div>
                <span>Patient Info</span>
              </div>
              <div className="flex-1 h-0.5 mx-2 bg-border" />
              <div
                className={`flex items-center gap-1.5 text-xs font-semibold ${
                  step >= 3 ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                    step === 3 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  3
                </div>
                <span>Confirm</span>
              </div>
            </div>
          )}
        </DialogHeader>

        {/* STEP 1: Doctor, Date & Slot */}
        {step === 1 && (
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="doctor-select" className="text-xs font-semibold flex items-center gap-1.5">
                  <Stethoscope className="w-3.5 h-3.5 text-muted-foreground" />
                  Select Doctor <span className="text-destructive">*</span>
                </Label>
                <select
                  id="doctor-select"
                  value={selectedDoctorId}
                  onChange={(e) => setSelectedDoctorId(e.target.value)}
                  disabled={loadingDoctors}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {doctors.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.name} ({doc.speciality} • {doc.department})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="date-input" className="text-xs font-semibold flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                  Appointment Date <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="date-input"
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  required
                />
              </div>
            </div>

            {selectedDoctor && (
              <div className="p-3 bg-muted/30 border border-border rounded-lg text-xs flex items-center justify-between">
                <div>
                  <span className="font-semibold text-foreground">{selectedDoctor.name}</span>
                  <span className="text-muted-foreground"> — {selectedDoctor.department} ({selectedDoctor.qualification})</span>
                </div>
                <Badge variant="outline" className="text-[11px]">
                  {selectedDoctor.slot_duration_minutes} min slots
                </Badge>
              </div>
            )}

            {/* Slots Grid */}
            <div className="space-y-2 pt-2">
              <Label className="text-xs font-semibold flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  Available Time Slots <span className="text-destructive">*</span>
                </span>
                <span className="text-muted-foreground text-[11px] font-normal">
                  {slots.length} open slots
                </span>
              </Label>

              {loadingSlots ? (
                <div className="flex items-center justify-center p-8 text-xs text-muted-foreground gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-primary" />
                  <span>Computing doctor availability...</span>
                </div>
              ) : slots.length === 0 ? (
                <div className="text-center p-6 border border-dashed border-border rounded-lg text-muted-foreground space-y-1">
                  <AlertCircle className="w-6 h-6 mx-auto text-amber-500" />
                  <p className="text-xs font-medium text-foreground">No available slots for this date</p>
                  <p className="text-[11px]">
                    The doctor may not be scheduled on this day, or all appointments are booked. Try selecting another date.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 max-h-48 overflow-y-auto p-1">
                  {slots.map((slot) => {
                    const isSelected = selectedSlot === slot.start;
                    return (
                      <button
                        key={slot.start}
                        type="button"
                        onClick={() => setSelectedSlot(slot.start)}
                        className={`px-2.5 py-2 text-xs font-medium rounded-lg border text-center transition-all cursor-pointer ${
                          isSelected
                            ? "bg-primary text-primary-foreground border-primary ring-2 ring-primary/30 font-semibold"
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
        )}

        {/* STEP 2: Patient Info */}
        {step === 2 && (
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="patient-name" className="text-xs font-semibold flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                  Patient Full Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="patient-name"
                  placeholder="e.g. Ramesh Chandra"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="patient-phone" className="text-xs font-semibold flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-muted-foreground" />
                  Phone Number <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="patient-phone"
                  placeholder="+919876543210"
                  value={patientPhone}
                  onChange={(e) => setPatientPhone(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="patient-age" className="text-xs font-semibold">
                  Age (years)
                </Label>
                <Input
                  id="patient-age"
                  type="number"
                  min="0"
                  max="125"
                  placeholder="e.g. 45"
                  value={patientAge}
                  onChange={(e) => setPatientAge(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="patient-gender" className="text-xs font-semibold">
                  Gender
                </Label>
                <select
                  id="patient-gender"
                  value={patientGender}
                  onChange={(e) => setPatientGender(e.target.value as Gender)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">Select gender (optional)</option>
                  <option value="MALE">Male</option>
                  <option value="FEMALE">Female</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="patient-email" className="text-xs font-semibold">
                  Email Address (optional)
                </Label>
                <Input
                  id="patient-email"
                  type="email"
                  placeholder="ramesh@example.com"
                  value={patientEmail}
                  onChange={(e) => setPatientEmail(e.target.value)}
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="booking-notes" className="text-xs font-semibold flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                  Visit Purpose / Clinical Notes
                </Label>
                <Textarea
                  id="booking-notes"
                  rows={2}
                  placeholder="e.g. Follow-up consultation for hypertension; brings recent blood test."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Review & Confirm */}
        {step === 3 && (
          <div className="space-y-4 py-2">
            <Card className="p-4 space-y-3 bg-muted/20 border-border">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Appointment Summary
              </h4>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-muted-foreground block">Consulting Doctor</span>
                  <span className="font-semibold text-foreground">{selectedDoctor?.name}</span>
                  <span className="text-muted-foreground block text-[11px]">{selectedDoctor?.department}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Date &amp; Scheduled Slot</span>
                  <span className="font-semibold text-foreground">{selectedDate}</span>
                  <span className="text-primary block font-medium">
                    {selectedSlot ? formatSlotTime(selectedSlot) : ""}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Patient</span>
                  <span className="font-semibold text-foreground">{patientName}</span>
                  <span className="text-muted-foreground block text-[11px]">
                    {patientAge ? `${patientAge} yrs` : ""} {patientGender ? `• ${patientGender}` : ""}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Contact Phone</span>
                  <span className="font-semibold text-foreground">{patientPhone}</span>
                </div>
              </div>

              {notes && (
                <div className="pt-2 border-t border-border/60 text-xs">
                  <span className="text-muted-foreground block text-[11px]">Clinical Notes:</span>
                  <p className="text-foreground italic">{notes}</p>
                </div>
              )}
            </Card>

            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>
                Confirming will issue a sequential token number for this doctor&apos;s daily OPD schedule.
              </span>
            </div>
          </div>
        )}

        {/* STEP 4: Confirmation Screen */}
        {step === 4 && confirmation && (
          <div className="py-6 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-foreground">Appointment Confirmed!</h3>
              <p className="text-sm text-muted-foreground">The token has been assigned and recorded in the database.</p>
            </div>

            <div className="inline-flex flex-col items-center justify-center p-4 rounded-2xl bg-primary/10 border border-primary/20 min-w-[200px]">
              <span className="text-xs uppercase tracking-wider font-semibold text-primary">Token Number</span>
              <span className="text-4xl font-extrabold text-primary flex items-center gap-1 mt-1">
                <Hash className="w-6 h-6" />
                {confirmation.token_number}
              </span>
            </div>

            <Card className="max-w-md mx-auto p-4 text-xs text-left space-y-2 bg-card">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Patient:</span>
                <span className="font-semibold text-foreground">{confirmation.patient_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Doctor:</span>
                <span className="font-semibold text-foreground">{confirmation.doctor_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Department:</span>
                <span className="font-semibold text-foreground">{confirmation.department}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Date &amp; Time:</span>
                <span className="font-semibold text-foreground">
                  {confirmation.appointment_date} at {formatSlotTime(confirmation.appointment_time)}
                </span>
              </div>
            </Card>
          </div>
        )}

        <DialogFooter className="flex items-center justify-between gap-2 pt-2 border-t border-border">
          {step <= 3 ? (
            <>
              {step > 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleBack}
                  disabled={isSubmitting}
                  className="gap-1 cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Back</span>
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  className="cursor-pointer"
                >
                  Cancel
                </Button>
              )}

              {step < 3 ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={handleNext}
                  disabled={(step === 1 && !canProceedStep1) || (step === 2 && !canProceedStep2)}
                  className="gap-1 cursor-pointer"
                >
                  <span>Next Step</span>
                  <ChevronRight className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={handleConfirmBooking}
                  disabled={isSubmitting}
                  className="gap-2 cursor-pointer bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Booking...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Confirm &amp; Issue Token</span>
                    </>
                  )}
                </Button>
              )}
            </>
          ) : (
            <Button
              type="button"
              className="w-full cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              Done &amp; Close
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
