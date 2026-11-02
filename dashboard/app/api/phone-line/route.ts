import { NextResponse } from "next/server";

export type PhoneLineState = "answering" | "needs_setup" | "offline" | "not_configured";

export async function GET() {
  const base = process.env.TELEPHONY_URL?.replace(/\/+$/, "");
  if (!base) return NextResponse.json({ state: "not_configured" satisfies PhoneLineState });
  try {
    const res = await fetch(`${base}/health`, { cache: "no-store", signal: AbortSignal.timeout(4000) });
    const health = (await res.json()) as { status?: string; hospital_configured?: boolean };
    const state: PhoneLineState =
      health.status === "ok" ? "answering" : health.hospital_configured === false ? "needs_setup" : "offline";
    return NextResponse.json({ state });
  } catch {
    return NextResponse.json({ state: "offline" satisfies PhoneLineState });
  }
}
