import { NextResponse } from "next/server";
import { TOKEN_COOKIE, apiUrl, cookieOptions } from "@/lib/auth/token";

// Signs in against the backend (the only place credentials are checked) and keeps the
// JWT it returns in an httpOnly cookie. The browser only ever receives the user's profile.
export async function POST(request: Request) {
  let body: { email?: unknown; password?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
  if (typeof body.email !== "string" || typeof body.password !== "string") {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }

  // Pass the browser's address along so the backend throttles per person, not per dashboard.
  const forwarded = request.headers.get("x-forwarded-for");
  let upstream: Response;
  try {
    upstream = await fetch(apiUrl("auth/login"), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(forwarded ? { "x-forwarded-for": forwarded } : {}),
      },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return NextResponse.json({ error: "The backend is not reachable" }, { status: 502 });
  }

  const data = (await upstream.json().catch(() => ({}))) as {
    access_token?: string;
    expires_in?: number;
    user?: unknown;
    detail?: unknown;
  };
  if (!upstream.ok || !data.access_token || !data.user) {
    const message =
      upstream.status === 401
        ? "Incorrect email or password"
        : typeof data.detail === "string"
          ? data.detail
          : upstream.status === 422
            ? "Enter a valid email address"
            : "Sign-in failed";
    const headers: Record<string, string> = {};
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    return NextResponse.json({ error: message }, { status: upstream.status || 502, headers });
  }

  const response = NextResponse.json({ user: data.user });
  response.cookies.set(TOKEN_COOKIE, data.access_token, cookieOptions(data.expires_in ?? 7200));
  return response;
}
