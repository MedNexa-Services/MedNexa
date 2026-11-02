"use client";

import * as React from "react";
import { toast } from "sonner";
import { updateHospital, type HospitalOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

const TIMEZONES = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "America/New_York", "UTC"];

function formFrom(h: HospitalOut) {
  return {
    name: h.name,
    address: h.address,
    phone: h.phone,
    email: h.email ?? "",
    opening_time: h.opening_time.slice(0, 5),
    closing_time: h.closing_time.slice(0, 5),
    timezone: h.timezone,
    general_instructions: h.general_instructions ?? "",
  };
}

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-[13px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function SettingsPage() {
  const { hospital, refreshHospital } = useHospital();
  const [form, setForm] = React.useState<ReturnType<typeof formFrom> | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const saved = React.useMemo(() => (hospital ? formFrom(hospital) : null), [hospital]);
  const values = form ?? saved;
  const dirty = form !== null && JSON.stringify(form) !== JSON.stringify(saved);

  React.useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (!hospital || !values) return <div className="h-96 animate-pulse rounded-lg border border-border bg-card" />;

  const set = (field: keyof typeof values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...values, [field]: e.target.value });

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!values || !hospital) return;
    if (values.closing_time <= values.opening_time) {
      toast.error("Closing time must be after opening time.");
      return;
    }
    setSaving(true);
    try {
      await updateHospital(hospital.id, {
        ...values,
        name: values.name.trim(),
        address: values.address.trim(),
        phone: values.phone.trim(),
        email: values.email.trim() || null,
        opening_time: `${values.opening_time}:00`,
        closing_time: `${values.closing_time}:00`,
        general_instructions: values.general_instructions.trim() || null,
      });
      await refreshHospital();
      setForm(null);
      toast.success("Settings saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Settings could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="The AI receptionist reads these details on every call, so callers hear them as written here."
      />

      <form onSubmit={onSubmit} className="max-w-2xl space-y-6">
        <section className="space-y-4 rounded-lg border border-border bg-card p-5">
          <h2 className="text-[15px] font-semibold">Hospital</h2>
          <Field id="name" label="Name">
            <Input id="name" required maxLength={200} value={values.name} onChange={set("name")} />
          </Field>
          <Field id="address" label="Address">
            <Textarea id="address" required rows={2} value={values.address} onChange={set("address")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="phone" label="Reception phone">
              <Input id="phone" type="tel" required minLength={3} maxLength={20} value={values.phone} onChange={set("phone")} />
            </Field>
            <Field id="email" label="Email (optional)">
              <Input id="email" type="email" value={values.email} onChange={set("email")} />
            </Field>
          </div>
        </section>

        <section className="space-y-4 rounded-lg border border-border bg-card p-5">
          <h2 className="text-[15px] font-semibold">OPD hours</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="opening_time" label="Opens">
              <Input id="opening_time" type="time" required value={values.opening_time} onChange={set("opening_time")} />
            </Field>
            <Field id="closing_time" label="Closes">
              <Input id="closing_time" type="time" required value={values.closing_time} onChange={set("closing_time")} />
            </Field>
            <Field id="timezone" label="Time zone">
              <NativeSelect id="timezone" value={values.timezone} onChange={set("timezone")}>
                {[...new Set([values.timezone, ...TIMEZONES])].map((tz) => (
                  <option key={tz}>{tz}</option>
                ))}
              </NativeSelect>
            </Field>
          </div>
          <p className="text-[13px] text-muted-foreground">
            Each doctor&apos;s own hours decide which slots can be booked; these are what callers are told.
          </p>
        </section>

        <section className="space-y-4 rounded-lg border border-border bg-card p-5">
          <h2 className="text-[15px] font-semibold">Receptionist</h2>
          <Field
            id="general_instructions"
            label="Notes for the receptionist"
            hint="Anything it should always know, such as 'Bring previous reports to every visit' or 'The OPD is closed on public holidays'."
          >
            <Textarea
              id="general_instructions"
              rows={4}
              value={values.general_instructions}
              onChange={set("general_instructions")}
            />
          </Field>
          <p className="text-[13px] text-muted-foreground">
            The receptionist speaks English and Hindi, and switches when the caller does.
          </p>
        </section>

        <div className="flex items-center gap-2">
          <Button type="submit" size="lg" disabled={!dirty || saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
          {dirty && (
            <Button type="button" variant="ghost" size="lg" onClick={() => setForm(null)} disabled={saving}>
              Discard changes
            </Button>
          )}
        </div>
      </form>

      <section className="mt-10 max-w-2xl border-t border-border pt-6">
        <h2 className="text-[15px] font-semibold">Phone line setup</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The telephony service needs this hospital&apos;s ID in MEDNEXA_TEL_HOSPITAL_ID to answer calls for it.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <code className="rounded-md border border-border bg-card px-2.5 py-1.5 font-mono text-[13px]">{hospital.id}</code>
          <Button
            variant="outline"
            onClick={async () => {
              await navigator.clipboard.writeText(hospital.id);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </section>
    </>
  );
}
