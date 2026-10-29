import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, getAuthSecret, verifySessionToken } from "@/lib/auth/session";

/** The signed-in staff user, read from the httpOnly session cookie. */
export async function GET(request: NextRequest) {
  const secret = getAuthSecret();
  const user = secret
    ? await verifySessionToken(request.cookies.get(SESSION_COOKIE)?.value, secret)
    : null;
  if (!user) {
    return NextResponse.json({ user: null }, { status: 401 });
  }
  return NextResponse.json({ user });
}
