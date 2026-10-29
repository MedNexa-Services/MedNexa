import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, getAuthSecret, verifySessionToken } from "@/lib/auth/session";

// Every page except /login needs a valid, unexpired, correctly signed session
// cookie. (Sessions are checked server-side here; the client-side AuthContext
// only mirrors the result for the UI.)
export async function proxy(request: NextRequest) {
  const secret = getAuthSecret();
  const user = secret
    ? await verifySessionToken(request.cookies.get(SESSION_COOKIE)?.value, secret)
    : null;
  if (user) {
    return NextResponse.next();
  }
  const login = new URL("/login", request.url);
  const response = NextResponse.redirect(login);
  response.cookies.delete(SESSION_COOKIE);
  return response;
}

export const config = {
  // Everything except the login page, the auth API, Next internals and static files.
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico)$).*)"],
};
