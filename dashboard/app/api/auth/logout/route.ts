import { NextResponse } from "next/server";
import { TOKEN_COOKIE, cookieOptions } from "@/lib/auth/token";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set(TOKEN_COOKIE, "", cookieOptions(0));
  return response;
}
