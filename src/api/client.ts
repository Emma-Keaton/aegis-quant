/**
 * API client — wraps fetch with session token auth.
 * The session token is obtained from /api/auth/init when the user starts the Mini App.
 */

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
}

async function apiFetch(url: string, options: FetchOptions = {}): Promise<Response> {
  const { requireAuth = true, headers: extraHeaders = {}, ...rest } = options;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...Object.fromEntries(Object.entries(extraHeaders).map(([k, v]) => [k, v])),
  };
  
  if (requireAuth) {
    const token = getSessionToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  
  return fetch(url, {
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
