"use client";

import * as React from "react";
import { useHospital } from "@/contexts/HospitalContext";
import { updateHospital, type HospitalUpdate } from "@/lib/api";
import { toast } from "sonner";
import {
  Building2,
  Clock,
  Globe2,
  Phone,
  Mail,
  MapPin,
  Save,
  RotateCcw,
  Check,
  Copy,
  AlertTriangle,
  Sparkles,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface LanguageOption {
  code: string;
  name: string;
  native: string;
}

const AVAILABLE_LANGUAGES: LanguageOption[] = [
  { code: "en", name: "English", native: "English" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "mr", name: "Marathi", native: "मराठी" },
  { code: "ta", name: "Tamil", native: "தமிழ்" },
  { code: "te", name: "Telugu", native: "తెలుగు" },
  { code: "bn", name: "Bengali", native: "বাংলা" },
  { code: "gu", name: "Gujarati", native: "ગુજરાતી" },
];

const TIMEZONES = [
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST — UTC+05:30)" },
  { value: "UTC", label: "UTC (Coordinated Universal Time — UTC+00:00)" },
  { value: "Asia/Dubai", label: "Asia/Dubai (GST — UTC+04:00)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (SGT — UTC+08:00)" },
  { value: "Europe/London", label: "Europe/London (GMT/BST)" },
  { value: "America/New_York", label: "America/New_York (EST/EDT — UTC-05:00)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (PST/PDT — UTC-08:00)" },
];

export default function SettingsPage() {
  const { hospital, hospitalId, isLoading, refreshHospital } = useHospital();

  const [formData, setFormData] = React.useState({
    name: "",
    address: "",
    phone: "",
    email: "",
    opening_time: "09:00",
    closing_time: "20:00",
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"] as string[],
    general_instructions: "",
    is_active: true,
  });

  const [initialData, setInitialData] = React.useState(formData);
  const [isSaving, setIsSaving] = React.useState(false);
  const [copiedId, setCopiedId] = React.useState(false);

  // Sync form state when hospital data is loaded
  React.useEffect(() => {
    if (hospital) {
      // Normalize times from HH:MM:SS to HH:MM for HTML time input
      const normOpen = hospital.opening_time ? hospital.opening_time.slice(0, 5) : "09:00";
      const normClose = hospital.closing_time ? hospital.closing_time.slice(0, 5) : "20:00";

      const data = {
        name: hospital.name || "",
        address: hospital.address || "",
        phone: hospital.phone || "",
        email: hospital.email || "",
        opening_time: normOpen,
        closing_time: normClose,
        timezone: hospital.timezone || "Asia/Kolkata",
        languages: Array.isArray(hospital.languages) ? hospital.languages : ["en", "hi"],
        general_instructions: hospital.general_instructions || "",
        is_active: hospital.is_active ?? true,
      };
      setFormData(data);
      setInitialData(data);
    }
  }, [hospital]);

  // Check if form has unsaved modifications
  const isDirty = React.useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(initialData);
  }, [formData, initialData]);

  // Warn user when attempting to leave or reload the page with unsaved changes
  React.useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved changes. Are you sure you want to leave?";
        return e.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  const handleLanguageToggle = (langCode: string) => {
    setFormData((prev) => {
      const exists = prev.languages.includes(langCode);
      if (exists) {
        if (prev.languages.length === 1) {
          toast.error("At least one language must be enabled for the AI receptionist.");
          return prev;
        }
        return { ...prev, languages: prev.languages.filter((l) => l !== langCode) };
      } else {
        return { ...prev, languages: [...prev.languages, langCode] };
      }
    });
  };

  const handleReset = () => {
    setFormData(initialData);
    toast.info("Reverted all unsaved changes.");
  };

  const handleCopyId = () => {
    if (hospitalId) {
      navigator.clipboard.writeText(hospitalId);
      setCopiedId(true);
      toast.success("Hospital ID copied to clipboard");
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hospitalId) {
      toast.error("Hospital ID not available");
      return;
    }

    if (!formData.name.trim()) {
      toast.error("Hospital name is required");
      return;
    }

    if (!formData.phone.trim()) {
      toast.error("Phone number is required");
      return;
    }

    if (formData.closing_time <= formData.opening_time) {
      toast.error("Closing time must be later than opening time");
      return;
    }

    if (formData.languages.length === 0) {
      toast.error("Please select at least one supported language");
      return;
    }

    setIsSaving(true);
    try {
      // Build clean payload with only modified values
      const payload: HospitalUpdate = {};

      if (formData.name !== initialData.name) payload.name = formData.name.trim();
      if (formData.address !== initialData.address) payload.address = formData.address.trim();
      if (formData.phone !== initialData.phone) payload.phone = formData.phone.trim();
      if (formData.email !== initialData.email) payload.email = formData.email.trim() || null;
      if (formData.opening_time !== initialData.opening_time) {
        payload.opening_time = `${formData.opening_time}:00`;
      }
      if (formData.closing_time !== initialData.closing_time) {
        payload.closing_time = `${formData.closing_time}:00`;
      }
      if (formData.timezone !== initialData.timezone) payload.timezone = formData.timezone;
      if (JSON.stringify(formData.languages) !== JSON.stringify(initialData.languages)) {
        payload.languages = formData.languages;
      }
      if (formData.general_instructions !== initialData.general_instructions) {
        payload.general_instructions = formData.general_instructions.trim() || null;
      }
      if (formData.is_active !== initialData.is_active) {
        payload.is_active = formData.is_active;
      }

      await updateHospital(hospitalId, payload);
      await refreshHospital();

      setInitialData(formData);
      toast.success("Hospital configuration updated successfully!");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update hospital settings";
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading && !hospital) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading hospital settings...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-5xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Building2 className="w-6 h-6 text-primary" />
            Hospital Settings &amp; AI Configuration
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage hospital identification, operating hours, active timezone, and AI receptionist voice language models.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isDirty && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleReset}
              disabled={isSaving}
              className="gap-1.5 cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reset</span>
            </Button>
          )}

          <Button
            type="submit"
            size="sm"
            disabled={!isDirty || isSaving}
            className="gap-2 cursor-pointer shadow-sm"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Save Changes</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Unsaved Changes Banner */}
      {isDirty && (
        <div className="flex items-center justify-between p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-sm">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>You have unsaved changes. Make sure to click <strong>Save Changes</strong> above to apply them across MedNexa.</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-xs text-amber-700 dark:text-amber-400 hover:bg-amber-500/20 h-7 px-2"
          >
            Discard
          </Button>
        </div>
      )}

      {/* Section 1: General Information */}
      <Card className="p-6 space-y-5">
        <div className="flex items-center gap-2.5 pb-2 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-semibold text-sm">
            1
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">General Facility Information</h2>
            <p className="text-xs text-muted-foreground">Primary hospital credentials displayed on caller transcripts and patient portals.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="hospital-name" className="text-xs font-semibold">
              Hospital Legal / Brand Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="hospital-name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. MedNexa City Hospital"
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="hospital-phone" className="text-xs font-semibold flex items-center gap-1.5">
              <Phone className="w-3.5 h-3.5 text-muted-foreground" />
              Reception Phone Number <span className="text-destructive">*</span>
            </Label>
            <Input
              id="hospital-phone"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="+917612400000"
              required
            />
            <p className="text-[11px] text-muted-foreground">E.164 formatted number used by Twilio/Exotel for voice calls.</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="hospital-email" className="text-xs font-semibold flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-muted-foreground" />
              Reception / Support Email
            </Label>
            <Input
              id="hospital-email"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="reception@mednexa.example"
            />
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="hospital-address" className="text-xs font-semibold flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-muted-foreground" />
              Hospital Address <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="hospital-address"
              rows={2}
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              placeholder="Full physical address including landmark, city, and pincode"
              required
            />
          </div>
        </div>
      </Card>

      {/* Section 2: Operating Hours & Timezone */}
      <Card className="p-6 space-y-5">
        <div className="flex items-center gap-2.5 pb-2 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-semibold text-sm">
            2
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Operational Hours &amp; Timezone</h2>
            <p className="text-xs text-muted-foreground">Determines daily OPD booking windows and slot computation boundaries.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="opening-time" className="text-xs font-semibold flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              OPD Opening Time <span className="text-destructive">*</span>
            </Label>
            <Input
              id="opening-time"
              type="time"
              value={formData.opening_time}
              onChange={(e) => setFormData({ ...formData, opening_time: e.target.value })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="closing-time" className="text-xs font-semibold flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              OPD Closing Time <span className="text-destructive">*</span>
            </Label>
            <Input
              id="closing-time"
              type="time"
              value={formData.closing_time}
              onChange={(e) => setFormData({ ...formData, closing_time: e.target.value })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="timezone-select" className="text-xs font-semibold flex items-center gap-1.5">
              <Globe2 className="w-3.5 h-3.5 text-muted-foreground" />
              Facility Timezone <span className="text-destructive">*</span>
            </Label>
            <select
              id="timezone-select"
              value={formData.timezone}
              onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            >
              {TIMEZONES.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-xs text-muted-foreground bg-muted/40 p-3 rounded-lg border border-border/50">
          💡 The AI telephone agent respects this timezone to convert caller intents like <em>&ldquo;Book an appointment this Thursday at 4 PM&rdquo;</em> into strict ISO 8601 UTC timestamps.
        </p>
      </Card>

      {/* Section 3: AI Receptionist & Multilingual Voice Settings */}
      <Card className="p-6 space-y-5">
        <div className="flex items-center gap-2.5 pb-2 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-semibold text-sm">
            3
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              AI Voice Agent &amp; Multilingual Recognition
              <Badge variant="outline" className="text-[10px] font-normal border-primary/30 text-primary bg-primary/5">
                <Sparkles className="w-3 h-3 mr-1" />
                Live Agent
              </Badge>
            </h2>
            <p className="text-xs text-muted-foreground">
              Select the spoken languages supported by the AI receptionist during live phone calls.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <Label className="text-xs font-semibold">
            Supported Spoken Languages <span className="text-destructive">*</span>
          </Label>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
            {AVAILABLE_LANGUAGES.map((lang) => {
              const isSelected = formData.languages.includes(lang.code);
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => handleLanguageToggle(lang.code)}
                  className={`flex items-center justify-between p-3 rounded-lg border text-left transition-all cursor-pointer ${
                    isSelected
                      ? "border-primary bg-primary/10 text-foreground ring-1 ring-primary"
                      : "border-border bg-card hover:bg-muted/50 text-muted-foreground"
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold">{lang.name}</span>
                    <span className="text-xs opacity-75">{lang.native}</span>
                  </div>
                  {isSelected ? (
                    <div className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full border border-border" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-1.5 pt-2">
          <Label htmlFor="general-instructions" className="text-xs font-semibold">
            AI Receptionist Clinical Instructions &amp; Patient Arrival Rules
          </Label>
          <Textarea
            id="general-instructions"
            rows={3}
            value={formData.general_instructions}
            onChange={(e) => setFormData({ ...formData, general_instructions: e.target.value })}
            placeholder="e.g. Patients should arrive 15 minutes before their scheduled slot. Fasting required for morning blood sugar tests."
          />
          <p className="text-[11px] text-muted-foreground">
            This prompt is dynamically injected into the AI voice agent&apos;s system prompt when confirming bookings or answering inquiries.
          </p>
        </div>
      </Card>

      {/* Section 4: System Information */}
      <Card className="p-6 space-y-4 bg-muted/20 border-border/80">
        <div className="flex items-center justify-between pb-2 border-b border-border/60">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-semibold text-foreground">Facility System Record</h3>
          </div>
          <Badge
            variant="outline"
            className={
              formData.is_active
                ? "border-emerald-500/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10"
                : "border-muted text-muted-foreground"
            }
          >
            {formData.is_active ? "Active Facility" : "Deactivated Facility"}
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="space-y-1">
            <span className="text-muted-foreground font-medium">Hospital Unique Identifier (UUID)</span>
            <div className="flex items-center gap-2">
              <code className="px-2 py-1 bg-background border border-border rounded font-mono text-xs select-all text-foreground">
                {hospitalId || "Not loaded"}
              </code>
              {hospitalId && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleCopyId}
                  className="h-7 px-2 cursor-pointer"
                >
                  {copiedId ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span className="sr-only">Copy ID</span>
                </Button>
              )}
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground font-medium">Facility Status</span>
            <div className="flex items-center gap-2 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-input text-primary focus:ring-primary w-4 h-4"
                />
                Accept appointments &amp; active AI telephony routing
              </label>
            </div>
          </div>
        </div>
      </Card>
    </form>
  );
}
