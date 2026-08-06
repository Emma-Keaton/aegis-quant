/**
 * API client — wraps fetch with Telegram initData + session token auth.
 * The session token is obtained from /api/auth/init when the user starts the Mini App.
 */

const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export function getApiBase(): string {
  return API_BASE;
}

export function getWebSocketUrl(): string {
  const base = API_BASE || window.location.origin;
  const proto = base.startsWith("https") ? "wss" : "ws";
  return `${proto}://${base.replace(/^https?:\/\//, "")}/ws/updates`;
}

/** Read Telegram WebApp initData, falling back to a ?tg_initData= query param (local dev). */
export function getInitData(): string {
  if (typeof window !== "undefined" && window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData;
  }
  const params = new URLSearchParams(window.location.search);
  return params.get("tg_initData") ?? "";
}

let sessionToken: string | null = null;

export function setSessionToken(token: string) {
  sessionToken = token;
  try {
    localStorage.setItem('aegis_session_token', token);
  } catch {}
}

export function getSessionToken(): string | null {
  if (sessionToken) return sessionToken;
  try {
    return localStorage.getItem('aegis_session_token');
  } catch {
    return null;
  }
}

export function clearSession() {
  sessionToken = null;
  try {
    localStorage.removeItem('aegis_session_token');
  } catch {}
}

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
  useInitData?: boolean;
}

function resolveUrl(url: string): string {
  return API_BASE ? `${API_BASE}${url}` : url;
}

export async function apiFetch(url: string, options: FetchOptions = {}): Promise<Response> {
  const { requireAuth = true, useInitData = true, headers: extraHeaders = {}, ...rest } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...Object.fromEntries(Object.entries(extraHeaders).map(([k, v]) => [k, v])),
  };

  if (useInitData) {
    const initData = getInitData();
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }
  }

  if (requireAuth) {
    const token = getSessionToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return fetch(resolveUrl(url), {
    ...rest,
    headers,
  });
}

// JSON helper — returns parsed JSON or throws
export async function apiJson<T = any>(url: string, options: FetchOptions = {}): Promise<T> {
  const res = await apiFetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as T;
}

export default apiFetch;
