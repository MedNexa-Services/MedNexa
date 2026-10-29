// The staff session is the backend's own JWT, held in an httpOnly cookie that only
// this server reads: browser code never sees the token. Server-side only.

export const TOKEN_COOKIE = "mednexa_token";

/** Where the dashboard *server* reaches the API (not the browser). */
export function backendUrl(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

/** `${backend}/api/v1/<path>` */
export function apiUrl(path: string): string {
  return `${backendUrl()}/api/v1/${path.replace(/^\/+/, "")}`;
}

export function cookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    // Browsers drop Secure cookies on plain HTTP; set AUTH_COOKIE_SECURE=false only for
    // an HTTP-only hospital LAN (HTTPS is strongly preferred).
    secure: process.env.AUTH_COOKIE_SECURE
      ? process.env.AUTH_COOKIE_SECURE === "true"
      : process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

/**
 * Whether the token's `exp` claim is still in the future. The signature is NOT
 * checked here (this server doesn't hold the signing key); the backend verifies it
 * on every request, so this only avoids showing pages to an obviously expired session.
 */
export function looksUnexpired(token: string | undefined): boolean {
  if (!token) return false;
  try {
    const body = token.split(".")[1];
    const json = atob(body.replace(/-/g, "+").replace(/_/g, "/"));
    const exp = (JSON.parse(json) as { exp?: unknown }).exp;
    return typeof exp === "number" && exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
