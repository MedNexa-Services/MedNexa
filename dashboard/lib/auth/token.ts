
export const TOKEN_COOKIE = "mednexa_token";

export function backendUrl(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  return `${backendUrl()}/api/v1/${path.replace(/^\/+/, "")}`;
}

export function cookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    secure: process.env.AUTH_COOKIE_SECURE
      ? process.env.AUTH_COOKIE_SECURE === "true"
      : process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

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
