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
import {
  createPatient,
  updatePatient,
  type PatientOut,
  type PatientCreate,
  type PatientUpdate,
  type Gender,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { toast } from "sonner";
import { User, Phone, Mail, MapPin, Loader2, Save } from "lucide-react";

interface PatientFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patient?: PatientOut | null; // If provided, edit mode
  onSuccess: () => void;
}

export function PatientFormDialog({
  open,
  onOpenChange,
  patient,
  onSuccess,
}: PatientFormDialogProps) {
  const { hospitalId } = useHospital();
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("+91");
  const [age, setAge] = React.useState<string>("");
  const [gender, setGender] = React.useState<Gender | "">("");
  const [email, setEmail] = React.useState("");
  const [address, setAddress] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      if (patient) {
        setName(patient.name || "");
        setPhone(patient.phone || "+91");
        setAge(patient.age ? String(patient.age) : "");
        setGender(patient.gender || "");
        setEmail(patient.email || "");
        setAddress(patient.address || "");
      } else {
        setName("");
        setPhone("+91");
        setAge("");
        setGender("");
        setEmail("");
        setAddress("");
      }
    }
  }, [open, patient]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Patient name is required");
      return;
    }
    if (!phone.trim() || phone.trim().length < 10) {
      toast.error("Valid phone number is required");
      return;
    }

    setIsSubmitting(true);
    try {
      if (patient) {
        const payload: PatientUpdate = {
          age: age ? parseInt(age, 10) : null,
          gender: gender ? (gender as Gender) : null,
          email: email.trim() || null,
          address: address.trim() || null,
        };
        await updatePatient(patient.id, payload);
        toast.success("Patient details updated successfully");
      } else {
        if (!hospitalId) {
          toast.error("Hospital ID not available");
          return;
        }
        const payload: PatientCreate = {
          hospital_id: hospitalId,
          name: name.trim(),
          phone: phone.trim(),
          age: age ? parseInt(age, 10) : null,
          gender: gender ? (gender as Gender) : null,
          email: email.trim() || null,
          address: address.trim() || null,
        };
        await createPatient(payload);
        toast.success("Patient registered successfully");
      }
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save patient";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <User className="w-4 h-4" />
              </div>
              <div>
                <DialogTitle className="text-base font-bold">
                  {patient ? "Edit Patient Profile" : "Register New Patient"}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  {patient
                    ? `Update record for ${patient.name}`
                    : "Add a patient to the hospital directory"}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-3.5 py-3 text-xs">
            <div className="space-y-1.5">
              <Label htmlFor="patient-form-name" className="text-xs font-semibold">
                Full Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="patient-form-name"
                placeholder="e.g. Ramesh Kumar"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!!patient} // name + phone identify the patient and can't be edited
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="patient-form-phone" className="text-xs font-semibold flex items-center gap-1">
                <Phone className="w-3.5 h-3.5 text-muted-foreground" />
                Phone Number <span className="text-destructive">*</span>
              </Label>
              <Input
                id="patient-form-phone"
                placeholder="+919876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                disabled={!!patient} // Phone is primary identity anchor in backend
                required
              />
              {patient && (
                <p className="text-[10px] text-muted-foreground">
                  Phone number is permanent patient identity key.
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="patient-form-age" className="text-xs font-semibold">
                  Age
                </Label>
                <Input
                  id="patient-form-age"
                  type="number"
                  min="0"
                  max="125"
                  placeholder="e.g. 42"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="patient-form-gender" className="text-xs font-semibold">
                  Gender
                </Label>
                <select
                  id="patient-form-gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value as Gender)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">Select gender</option>
                  <option value="MALE">Male</option>
                  <option value="FEMALE">Female</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="patient-form-email" className="text-xs font-semibold flex items-center gap-1">
                <Mail className="w-3.5 h-3.5 text-muted-foreground" />
                Email Address
              </Label>
              <Input
                id="patient-form-email"
                type="email"
                placeholder="ramesh@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="patient-form-address" className="text-xs font-semibold flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-muted-foreground" />
                Residential Address
              </Label>
              <Textarea
                id="patient-form-address"
                rows={2}
                placeholder="Street address, city, pincode"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter className="border-t border-border pt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="gap-1.5 cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5" />
                  <span>{patient ? "Update Profile" : "Register Patient"}</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
