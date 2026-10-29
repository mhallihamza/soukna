// Client API : token localStorage + en-tête Authorization + gestion 401.
"use client";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Auth = { token: string; role: "admin" | "entreprise" };

const KEY = "soukna_auth";

export function getAuth(): Auth | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Auth) : null;
  } catch {
    return null;
  }
}

export function setAuth(auth: Auth) {
  window.localStorage.setItem(KEY, JSON.stringify(auth));
}

export function clearAuth() {
  window.localStorage.removeItem(KEY);
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const auth = getAuth();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (auth) headers.Authorization = `Bearer ${auth.token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expirée");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* corps non JSON */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}
