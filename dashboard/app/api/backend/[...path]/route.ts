import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, apiUrl } from "@/lib/auth/token";

// Same-origin gateway to the backend API: the browser calls /api/backend/<path>, and this
// server forwards it to <BACKEND_URL>/api/v1/<path> with the staff token from the httpOnly
// cookie. The token never reaches browser JavaScript, and staff machines don't need to
// reach the API directly.

const FORWARDED_REQUEST_HEADERS = ["content-type", "accept", "accept-language"];
const SAFE_METHODS = new Set(["GET", "HEAD"]);

async function forward(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  // Segments are appended to a fixed prefix: refuse anything that could climb out of
  // /api/v1 or reach the unauthenticated auth routes through the gateway.
  if (path.some((s) => s === "." || s === ".." || /[\\/]/.test(s)) || path[0] === "auth") {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  // Defence in depth on top of SameSite=Lax: state-changing requests must come from this site.
  if (!SAFE_METHODS.has(request.method)) {
    const origin = request.headers.get("origin");
    if (origin && new URL(origin).host !== request.headers.get("host")) {
      return NextResponse.json({ error: "Cross-site request refused" }, { status: 403 });
    }
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) return NextResponse.json({ error: "Not signed in" }, { status: 401 });

  const headers = new Headers({ authorization: `Bearer ${token}` });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const target = `${apiUrl(path.map(encodeURIComponent).join("/"))}${request.nextUrl.search}`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: SAFE_METHODS.has(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    return NextResponse.json({ error: { message: "The backend is not reachable" } }, { status: 502 });
  }

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  const correlation = upstream.headers.get("x-correlation-id");
  if (correlation) responseHeaders.set("x-correlation-id", correlation);
  return new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
