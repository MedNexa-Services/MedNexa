import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, apiUrl, cookieOptions } from "@/lib/auth/token";

/** The signed-in staff user, as verified by the backend (it checks the token's signature). */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) return NextResponse.json({ user: null }, { status: 401 });

  let upstream: Response;
  try {
    upstream = await fetch(apiUrl("auth/me"), {
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return NextResponse.json({ user: null, error: "The backend is not reachable" }, { status: 502 });
  }
  if (!upstream.ok) {
    const response = NextResponse.json({ user: null }, { status: 401 });
    if (upstream.status === 401) response.cookies.set(TOKEN_COOKIE, "", cookieOptions(0));
    return response;
  }
  return NextResponse.json({ user: await upstream.json() });
}
