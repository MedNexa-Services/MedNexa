import axios from "axios";

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
  if (typeof body.error === "string") return body.error;
  if (body.error && typeof body.error === "object") {
    const message = (body.error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": ")
      )
      .join("; ");
  }
  return undefined;
}

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
