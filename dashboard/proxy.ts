import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, looksUnexpired } from "@/lib/auth/token";

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
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico)$).*)"],
};
