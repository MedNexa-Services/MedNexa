import { NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  createSessionToken,
  getAuthSecret,
  safeEqual,
  type StaffUser,
} from "@/lib/auth/session";

// Staff credentials are checked here, on the server; they never reach the browser.
// Part 5 replaces this single staff account with backend-issued JWTs (plan task 5.3).
export async function POST(request: Request) {
  const secret = getAuthSecret();
  const staffEmail = process.env.STAFF_EMAIL;
  const staffPassword = process.env.STAFF_PASSWORD;
  if (!secret || !staffEmail || !staffPassword) {
    return NextResponse.json(
      {
        error:
          "Sign-in is not configured. Set AUTH_SECRET (32+ characters), STAFF_EMAIL and STAFF_PASSWORD on the dashboard server.",
      },
      { status: 503 }
    );
  }

  let email = "";
  let password = "";
  try {
    const body = (await request.json()) as { email?: unknown; password?: unknown };
    email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
    password = typeof body.password === "string" ? body.password : "";
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }

  // Compare both fields every time so the response time doesn't reveal which was wrong.
  const [emailOk, passwordOk] = await Promise.all([
    safeEqual(email, staffEmail.trim().toLowerCase()),
    safeEqual(password, staffPassword),
  ]);
  if (!emailOk || !passwordOk) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const user: StaffUser = {
    email: staffEmail,
    name: process.env.STAFF_NAME || "Hospital Staff",
    role: "Hospital Staff",
  };
  const response = NextResponse.json({ user });
  response.cookies.set(SESSION_COOKIE, await createSessionToken(user, secret), {
    httpOnly: true,
    // Browsers drop Secure cookies on plain HTTP; set AUTH_COOKIE_SECURE=false only for
    // an HTTP-only hospital LAN (HTTPS is strongly preferred, see plan §5 security).
    secure: process.env.AUTH_COOKIE_SECURE
      ? process.env.AUTH_COOKIE_SECURE === "true"
      : process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return response;
}
