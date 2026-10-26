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
import { createDoctor, updateDoctor, type DoctorCreate, type DoctorOut, type DoctorUpdate } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { toast } from "sonner";
import { Stethoscope, Clock, Calendar, Check, AlertCircle } from "lucide-react";

interface DoctorFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  doctor?: DoctorOut | null; // If passed, edit mode; else create mode
  onSuccess: () => void;
}

const WEEKDAYS = [
  { day: 1, label: "Mon", full: "Monday" },
  { day: 2, label: "Tue", full: "Tuesday" },
  { day: 3, label: "Wed", full: "Wednesday" },
  { day: 4, label: "Thu", full: "Thursday" },
  { day: 5, label: "Fri", full: "Friday" },
  { day: 6, label: "Sat", full: "Saturday" },
  { day: 7, label: "Sun", full: "Sunday" },
];

const COMMON_DEPARTMENTS = [
  "General Medicine",
  "Cardiology",
  "Orthopedics",
  "Pediatrics",
  "Neurology",
  "Dermatology",
  "ENT",
  "Gynecology",
];

export function DoctorFormDialog({
  open,
  onOpenChange,
  doctor,
  onSuccess,
}: DoctorFormDialogProps) {
  const { hospitalId } = useHospital();
  const isEditing = !!doctor;

  const [name, setName] = React.useState("");
  const [speciality, setSpeciality] = React.useState("");
  const [qualification, setQualification] = React.useState("");
  const [department, setDepartment] = React.useState("");
  const [maxDailyAppointments, setMaxDailyAppointments] = React.useState(16);
  const [slotDurationMinutes, setSlotDurationMinutes] = React.useState(15);
  const [availableDays, setAvailableDays] = React.useState<number[]>([1, 2, 3, 4, 5]);
  const [slotStartTime, setSlotStartTime] = React.useState("09:00");
  const [slotEndTime, setSlotEndTime] = React.useState("13:00");
  const [bio, setBio] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Initialize or reset form when modal opens or doctor changes
  React.useEffect(() => {
    if (doctor) {
      setName(doctor.name);
      setSpeciality(doctor.speciality);
      setQualification(doctor.qualification || "");
      setDepartment(doctor.department);
      setMaxDailyAppointments(doctor.max_daily_appointments);
      setSlotDurationMinutes(doctor.slot_duration_minutes);
      setAvailableDays(doctor.available_days || [1, 2, 3, 4, 5]);
      setSlotStartTime(doctor.slot_start_time.substring(0, 5));
      setSlotEndTime(doctor.slot_end_time.substring(0, 5));
      setBio(doctor.bio || "");
    } else {
      setName("");
      setSpeciality("");
      setQualification("");
      setDepartment("");
      setMaxDailyAppointments(16);
      setSlotDurationMinutes(15);
      setAvailableDays([1, 2, 3, 4, 5]);
      setSlotStartTime("09:00");
      setSlotEndTime("13:00");
      setBio("");
    }
    setError(null);
  }, [doctor, open]);

  const toggleDay = (day: number) => {
    if (availableDays.includes(day)) {
      if (availableDays.length === 1) {
        toast.warning("Doctor must have at least one working day");
        return;
      }
      setAvailableDays(availableDays.filter((d) => d !== day));
    } else {
      setAvailableDays([...availableDays, day].sort());
    }
  };

  const selectAllWeekdays = () => {
    setAvailableDays([1, 2, 3, 4, 5]);
  };

  const selectAllDays = () => {
    setAvailableDays([1, 2, 3, 4, 5, 6, 7]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!name.trim()) {
      setError("Doctor name is required");
      return;
    }
    if (!speciality.trim()) {
      setError("Speciality is required");
      return;
    }
    if (!department.trim()) {
      setError("Department is required");
      return;
    }
    if (availableDays.length === 0) {
      setError("Select at least one working day");
      return;
    }
    if (slotEndTime <= slotStartTime) {
      setError("Shift end time must be after shift start time");
      return;
    }

    const formatTimeToApi = (t: string) => (t.length === 5 ? `${t}:00` : t);

    setIsSubmitting(true);
    try {
      if (isEditing && doctor) {
        const payload: DoctorUpdate = {
          name: name.trim(),
          speciality: speciality.trim(),
          qualification: qualification.trim() || null,
          department: department.trim(),
          max_daily_appointments: Number(maxDailyAppointments),
          slot_duration_minutes: Number(slotDurationMinutes),
          available_days: availableDays,
          slot_start_time: formatTimeToApi(slotStartTime),
          slot_end_time: formatTimeToApi(slotEndTime),
          bio: bio.trim() || null,
        };

        await updateDoctor(doctor.id, payload);
        toast.success(`Updated Dr. ${name}`);
      } else {
        if (!hospitalId) {
          setError("No active hospital found in context.");
          return;
        }

        const payload: DoctorCreate = {
          hospital_id: hospitalId,
          name: name.trim(),
          speciality: speciality.trim(),
          qualification: qualification.trim() || null,
          department: department.trim(),
          max_daily_appointments: Number(maxDailyAppointments),
          slot_duration_minutes: Number(slotDurationMinutes),
          available_days: availableDays,
          slot_start_time: formatTimeToApi(slotStartTime),
          slot_end_time: formatTimeToApi(slotEndTime),
          bio: bio.trim() || null,
        };

        await createDoctor(payload);
        toast.success(`Registered Dr. ${name}`);
      }

      onOpenChange(false);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save doctor details";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
            <Stethoscope className="w-5 h-5" />
            <DialogTitle className="text-lg font-bold">
              {isEditing ? `Edit ${doctor?.name}` : "Add New Doctor"}
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            {isEditing
              ? "Update medical credentials, schedule capacity, and shift availability."
              : "Register a new practitioner to the hospital roster for AI voice receptionist bookings."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs animate-in fade-in">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          {/* Row 1: Name & Qualification */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2 space-y-1.5">
              <Label htmlFor="doc-name" className="text-xs font-semibold">
                Doctor Name *
              </Label>
              <Input
                id="doc-name"
                placeholder="Dr. Rajesh Verma"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="doc-qual" className="text-xs font-semibold">
                Qualification
              </Label>
              <Input
                id="doc-qual"
                placeholder="MBBS, MS"
                value={qualification}
                onChange={(e) => setQualification(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          {/* Row 2: Speciality & Department */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="doc-speciality" className="text-xs font-semibold">
                Speciality *
              </Label>
              <Input
                id="doc-speciality"
                placeholder="Cardiologist, Pediatrician..."
                value={speciality}
                onChange={(e) => setSpeciality(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="doc-dept" className="text-xs font-semibold">
                Department *
              </Label>
              <Input
                id="doc-dept"
                placeholder="Cardiology, General Medicine..."
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                list="dept-suggestions"
                required
                className="h-9 text-xs"
              />
              <datalist id="dept-suggestions">
                {COMMON_DEPARTMENTS.map((dept) => (
                  <option key={dept} value={dept} />
                ))}
              </datalist>
            </div>
          </div>

          {/* Row 3: Available Days Checkbox Grid */}
          <div className="space-y-2 pt-1 border-t border-border">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-blue-500" />
                <span>Working Days Template *</span>
              </Label>
              <div className="flex items-center gap-2 text-[11px] text-blue-600 dark:text-blue-400">
                <button
                  type="button"
                  onClick={selectAllWeekdays}
                  className="hover:underline cursor-pointer"
                >
                  Mon–Fri
                </button>
                <span>•</span>
                <button
                  type="button"
                  onClick={selectAllDays}
                  className="hover:underline cursor-pointer"
                >
                  All Days
                </button>
              </div>
            </div>

            <div className="grid grid-cols-7 gap-1.5">
              {WEEKDAYS.map((w) => {
                const isSelected = availableDays.includes(w.day);
                return (
                  <button
                    key={w.day}
                    type="button"
                    onClick={() => toggleDay(w.day)}
                    className={`py-2 px-1 rounded-lg text-xs font-semibold transition-all flex flex-col items-center justify-center gap-0.5 cursor-pointer border ${
                      isSelected
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-background text-muted-foreground border-border hover:bg-muted"
                    }`}
                  >
                    <span>{w.label}</span>
                    {isSelected && <Check className="w-3 h-3" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Row 4: Shift Hours & Capacity */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 border-t border-border">
            <div className="space-y-1.5">
              <Label htmlFor="start-time" className="text-xs font-semibold flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                <span>Shift Start</span>
              </Label>
              <Input
                id="start-time"
                type="time"
                value={slotStartTime}
                onChange={(e) => setSlotStartTime(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="end-time" className="text-xs font-semibold flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                <span>Shift End</span>
              </Label>
              <Input
                id="end-time"
                type="time"
                value={slotEndTime}
                onChange={(e) => setSlotEndTime(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="slot-duration" className="text-xs font-semibold">
                Slot Length
              </Label>
              <div className="relative">
                <Input
                  id="slot-duration"
                  type="number"
                  min="5"
                  max="120"
                  value={slotDurationMinutes}
                  onChange={(e) => setSlotDurationMinutes(Number(e.target.value))}
                  required
                  className="h-9 text-xs pr-10"
                />
                <span className="absolute right-2.5 top-2.5 text-[11px] text-muted-foreground">
                  min
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="max-cap" className="text-xs font-semibold">
                Daily Cap
              </Label>
              <div className="relative">
                <Input
                  id="max-cap"
                  type="number"
                  min="1"
                  max="200"
                  value={maxDailyAppointments}
                  onChange={(e) => setMaxDailyAppointments(Number(e.target.value))}
                  required
                  className="h-9 text-xs pr-10"
                />
                <span className="absolute right-2.5 top-2.5 text-[11px] text-muted-foreground">
                  slots
                </span>
              </div>
            </div>
          </div>

          {/* Row 5: Bio (Optional) */}
          <div className="space-y-1.5 pt-1">
            <Label htmlFor="doc-bio" className="text-xs font-semibold">
              Doctor Bio / Notes (Optional)
            </Label>
            <Textarea
              id="doc-bio"
              placeholder="Specialized in non-invasive cardiology and interventional patient care."
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={2}
              className="text-xs resize-none"
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="text-xs h-9 cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="text-xs h-9 bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer"
            >
              {isSubmitting
                ? "Saving..."
                : isEditing
                ? "Save Changes"
                : "Create Doctor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
