import axios from "axios";

// Requests go to this site's own /api/backend gateway, which forwards them to the API
// with the staff token from an httpOnly cookie (see app/api/backend). No API URL or
// token is needed in the browser.
export const apiClient = axios.create({
  baseURL: "/api/backend",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

function messageFrom(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return undefined;
  const body = data as { error?: unknown; detail?: unknown };
  if (typeof body.error === "string") return body.error; // from the gateway
  if (body.error && typeof body.error === "object") {
    const message = (body.error as { message?: unknown }).message; // from the API
    if (typeof message === "string") return message;
  }
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    // FastAPI validation errors: [{ loc, msg }, ...]
    return body.detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": ")
      )
      .join("; ");
  }
  return undefined;
}

// Normalise errors, and send people whose session ended back to the sign-in page.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      window.location.pathname !== "/login"
    ) {
      window.location.assign("/login");
    }
    return Promise.reject(
      new Error(messageFrom(error.response?.data) ?? error.message ?? "Unknown error")
    );
  }
);
