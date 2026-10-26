"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Stethoscope,
  Calendar,
  Clock,
  Save,
  Trash2,
  Check,
  AlertCircle,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";
import { getDoctor, updateDoctor, deleteDoctor, type DoctorDetailOut, type DoctorUpdate } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

const WEEKDAYS = [
  { day: 1, label: "Mon", full: "Monday" },
  { day: 2, label: "Tue", full: "Tuesday" },
  { day: 3, label: "Wed", full: "Wednesday" },
  { day: 4, label: "Thu", full: "Thursday" },
  { day: 5, label: "Fri", full: "Friday" },
  { day: 6, label: "Sat", full: "Saturday" },
  { day: 7, label: "Sun", full: "Sunday" },
];

export default function DoctorDetailPage() {
  const params = useParams();
  const router = useRouter();
  const doctorId = Array.isArray(params.id) ? params.id[0] : (params.id as string);

  const [doctor, setDoctor] = React.useState<DoctorDetailOut | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Form Fields
  const [name, setName] = React.useState("");
  const [speciality, setSpeciality] = React.useState("");
  const [qualification, setQualification] = React.useState("");
  const [department, setDepartment] = React.useState("");
  const [maxDailyAppointments, setMaxDailyAppointments] = React.useState(16);
  const [slotDurationMinutes, setSlotDurationMinutes] = React.useState(15);
  const [availableDays, setAvailableDays] = React.useState<number[]>([1, 2, 3, 4, 5]);
  const [slotStartTime, setSlotStartTime] = React.useState("09:00");
  const [slotEndTime, setSlotEndTime] = React.useState("13:00");
  const [isActive, setIsActive] = React.useState(true);
  const [bio, setBio] = React.useState("");

  const loadDoctor = React.useCallback(async () => {
    if (!doctorId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDoctor(doctorId);
      setDoctor(data);
      setName(data.name);
      setSpeciality(data.speciality);
      setQualification(data.qualification || "");
      setDepartment(data.department);
      setMaxDailyAppointments(data.max_daily_appointments);
      setSlotDurationMinutes(data.slot_duration_minutes);
      setAvailableDays(data.available_days || [1, 2, 3, 4, 5]);
      setSlotStartTime(data.slot_start_time.substring(0, 5));
      setSlotEndTime(data.slot_end_time.substring(0, 5));
      setIsActive(data.is_active);
      setBio(data.bio || "");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load doctor profile";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [doctorId]);

  React.useEffect(() => {
    loadDoctor();
  }, [loadDoctor]);

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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!doctorId) return;
    setError(null);

    if (slotEndTime <= slotStartTime) {
      setError("Shift end time must be after start time");
      return;
    }

    const formatTimeToApi = (t: string) => (t.length === 5 ? `${t}:00` : t);

    setIsSaving(true);
    try {
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
        is_active: isActive,
        bio: bio.trim() || null,
      };

      await updateDoctor(doctorId, payload);
      toast.success("Doctor details saved successfully");
      loadDoctor();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save changes";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!doctorId) return;
    setIsDeleting(true);
    try {
      await deleteDoctor(doctorId);
      toast.success("Doctor deactivated successfully");
      router.replace("/doctors");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to deactivate doctor";
      toast.error(msg);
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-12 text-center space-y-3">
        <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-xs text-muted-foreground">Loading doctor details...</p>
      </div>
    );
  }

  if (!doctor && error) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
        <h3 className="text-base font-bold text-foreground">Doctor Not Found</h3>
        <p className="text-xs text-muted-foreground">{error}</p>
        <Link
          href="/doctors"
          className="inline-flex items-center px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-medium text-foreground transition-colors"
        >
          Back to Doctors Roster
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link
              href="/doctors"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Doctors Roster</span>
            </Link>
            <span className="text-muted-foreground text-xs">/</span>
            <span className="text-xs font-semibold text-foreground">{doctor?.name}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>{doctor?.name}</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20"
                  : "bg-muted text-muted-foreground border-border"
              }`}
            >
              {isActive ? "Active" : "Inactive"}
            </span>
          </h1>
        </div>

        {/* Schedule Overrides Navigation Link */}
        <div className="flex items-center gap-2">
          <Link
            href={`/doctors/${doctorId}/schedule`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-medium text-foreground transition-colors"
          >
            <Calendar className="w-3.5 h-3.5 text-blue-500" />
            <span>Schedule Overrides</span>
            <ExternalLink className="w-3 h-3 text-muted-foreground" />
          </Link>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Main Details Card */}
        <Card className="p-6 border-border bg-card shadow-xs space-y-5">
          <div className="flex items-center gap-2 pb-3 border-b border-border font-semibold text-sm text-foreground">
            <Stethoscope className="w-4 h-4 text-blue-600" />
            <span>Practitioner Information</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="edit-name" className="text-xs font-semibold">
                Doctor Full Name *
              </Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit-qual" className="text-xs font-semibold">
                Qualifications
              </Label>
              <Input
                id="edit-qual"
                value={qualification}
                onChange={(e) => setQualification(e.target.value)}
                placeholder="e.g. MBBS, MD, DM"
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit-spec" className="text-xs font-semibold">
                Speciality *
              </Label>
              <Input
                id="edit-spec"
                value={speciality}
                onChange={(e) => setSpeciality(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit-dept" className="text-xs font-semibold">
                Department *
              </Label>
              <Input
                id="edit-dept"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>
          </div>

          {/* Active Status Checkbox */}
          <div className="pt-2 flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30">
            <div>
              <p className="text-xs font-semibold text-foreground">
                Active Receptionist Availability
              </p>
              <p className="text-[11px] text-muted-foreground">
                When active, the AI receptionist will suggest this doctor to callers booking appointments.
              </p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-4 h-4 rounded border-border text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <span className="text-xs font-medium text-foreground">
                {isActive ? "Active" : "Inactive"}
              </span>
            </label>
          </div>
        </Card>

        {/* Weekly Schedule Template Card */}
        <Card className="p-6 border-border bg-card shadow-xs space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2 font-semibold text-sm text-foreground">
              <Calendar className="w-4 h-4 text-blue-600" />
              <span>Weekly Shift Template</span>
            </div>
            <span className="text-xs text-muted-foreground">
              Recurring schedule applied automatically
            </span>
          </div>

          {/* Available Days Grid */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold">Working Days Template *</Label>
            <div className="grid grid-cols-7 gap-2">
              {WEEKDAYS.map((w) => {
                const isSelected = availableDays.includes(w.day);
                return (
                  <button
                    key={w.day}
                    type="button"
                    onClick={() => toggleDay(w.day)}
                    className={`py-2 px-1 rounded-lg text-xs font-semibold transition-all flex flex-col items-center justify-center gap-1 cursor-pointer border ${
                      isSelected
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-background text-muted-foreground border-border hover:bg-muted"
                    }`}
                  >
                    <span>{w.label}</span>
                    {isSelected && <Check className="w-3.5 h-3.5" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Shift Hours & Capacity */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="shift-start" className="text-xs font-semibold flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                <span>Shift Start</span>
              </Label>
              <Input
                id="shift-start"
                type="time"
                value={slotStartTime}
                onChange={(e) => setSlotStartTime(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="shift-end" className="text-xs font-semibold flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                <span>Shift End</span>
              </Label>
              <Input
                id="shift-end"
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
                Max Daily Cap
              </Label>
              <div className="relative">
                <Input
                  id="max-cap"
                  type="number"
                  min="1"
                  max="500"
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

          <div className="space-y-1.5 pt-2">
            <Label htmlFor="edit-bio" className="text-xs font-semibold">
              Doctor Bio / Consultation Notes
            </Label>
            <Textarea
              id="edit-bio"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={3}
              placeholder="Provide background, clinical interests, or specific hospital instructions for receptionists."
              className="text-xs"
            />
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setIsDeleteDialogOpen(true)}
            className="text-xs text-destructive hover:bg-destructive/10 hover:border-destructive/30 cursor-pointer gap-1.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Deactivate Doctor</span>
          </Button>

          <div className="flex items-center gap-3">
            <Link
              href="/doctors"
              className="px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-medium text-foreground transition-colors cursor-pointer"
            >
              Cancel
            </Link>
            <Button
              type="submit"
              size="sm"
              disabled={isSaving}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer gap-1.5"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isSaving ? "Saving Changes..." : "Save Doctor Profile"}</span>
            </Button>
          </div>
        </div>
      </form>

      {/* Delete / Deactivate Confirmation Dialog */}
      <Dialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-destructive">
              <ShieldAlert className="w-5 h-5" />
              <DialogTitle className="text-base font-bold">
                Deactivate {doctor?.name}?
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1">
              This will mark the practitioner inactive. Future slots will no longer be offered to callers by the AI agent.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="pt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteDialogOpen(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={isDeleting}
              onClick={handleDelete}
              className="text-xs gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{isDeleting ? "Deactivating..." : "Confirm Deactivation"}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
