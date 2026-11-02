"use client";

import * as React from "react";
import { createHospital } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function HospitalSetup() {
  const { refreshHospital } = useHospital();
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    setSaving(true);
    setError(null);
    try {
      await createHospital({
        name: text("name"),
        address: text("address"),
        phone: text("phone"),
        email: text("email") || null,
        opening_time: text("opening_time"),
        closing_time: text("closing_time"),
        languages: ["en", "hi"],
      });
      await refreshHospital();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The hospital could not be saved.");
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg py-10">
      <h1 className="text-[22px] font-semibold">Set up your hospital</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        The AI receptionist reads these details on every call. You can change them later in
        Settings, then add doctors and their hours.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded-lg border border-border bg-card p-6">
        <div className="space-y-1.5">
          <Label htmlFor="name">Hospital name</Label>
          <Input id="name" name="name" required maxLength={200} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="address">Address</Label>
          <Input id="address" name="address" required />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="phone">Reception phone</Label>
            <Input id="phone" name="phone" type="tel" required minLength={3} maxLength={20} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email (optional)</Label>
            <Input id="email" name="email" type="email" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="opening_time">OPD opens</Label>
            <Input id="opening_time" name="opening_time" type="time" defaultValue="09:00" required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="closing_time">OPD closes</Label>
            <Input id="closing_time" name="closing_time" type="time" defaultValue="18:00" required />
          </div>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={saving}>
          {saving ? "Saving…" : "Save and continue"}
        </Button>
      </form>
    </div>
  );
}
