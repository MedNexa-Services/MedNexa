import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, looksUnexpired } from "@/lib/auth/token";

// Pages need a session cookie whose token hasn't expired; otherwise the user is sent to
// /login (and API calls get a 401). The backend still verifies the token's signature on
// every API request, so this is a convenience check, not the security boundary.
export function proxy(request: NextRequest) {
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (looksUnexpired(token)) {
    return NextResponse.next();
  }
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  const response = NextResponse.redirect(new URL("/login", request.url));
  if (token) response.cookies.delete(TOKEN_COOKIE);
  return response;
}

export const config = {
  // Everything except the login page, the auth API, Next internals and static files.
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico)$).*)"],
};
