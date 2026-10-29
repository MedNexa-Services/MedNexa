// Stateless staff session: an HMAC-SHA256-signed token in an httpOnly cookie.
// Used only on the server (route handlers and proxy.ts); never import it from
// client components. Works in both the Node.js and Edge runtimes (Web Crypto).

export const SESSION_COOKIE = "mednexa_session";
export const SESSION_TTL_SECONDS = 8 * 60 * 60; // one shift

export interface StaffUser {
  email: string;
  name: string;
  role: string;
}

interface SessionPayload extends StaffUser {
  exp: number; // unix seconds
}

const encoder = new TextEncoder();

function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64url(text: string): Uint8Array {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/** The signing secret; at least 32 characters, from the server-only AUTH_SECRET. */
export function getAuthSecret(): string | null {
  const secret = process.env.AUTH_SECRET;
  return secret && secret.length >= 32 ? secret : null;
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

export async function createSessionToken(user: StaffUser, secret: string): Promise<string> {
  const payload: SessionPayload = {
    ...user,
    exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS,
  };
  const body = base64url(encoder.encode(JSON.stringify(payload)));
  const signature = await crypto.subtle.sign("HMAC", await hmacKey(secret), encoder.encode(body));
  return `${body}.${base64url(new Uint8Array(signature))}`;
}

/** The session's user, or null if the token is missing, tampered with or expired. */
export async function verifySessionToken(
  token: string | undefined,
  secret: string
): Promise<StaffUser | null> {
  if (!token) return null;
  const [body, signature, extra] = token.split(".");
  if (!body || !signature || extra !== undefined) return null;
  try {
    const valid = await crypto.subtle.verify(
      "HMAC",
      await hmacKey(secret),
      fromBase64url(signature) as BufferSource,
      encoder.encode(body)
    );
    if (!valid) return null;
    const payload = JSON.parse(new TextDecoder().decode(fromBase64url(body))) as SessionPayload;
    if (typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now()) return null;
    return { email: payload.email, name: payload.name, role: payload.role };
  } catch {
    return null;
  }
}

/** Constant-time string comparison (via SHA-256 digests, so lengths don't leak). */
export async function safeEqual(a: string, b: string): Promise<boolean> {
  const [da, db] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(a)),
    crypto.subtle.digest("SHA-256", encoder.encode(b)),
  ]);
  const x = new Uint8Array(da);
  const y = new Uint8Array(db);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}
