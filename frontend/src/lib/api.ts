// Axios API client with timeout, in-flight dedupe and auto-refresh
// Path: frontend/src/lib/api.ts
import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── In-flight GET dedupe ─────────────────────────────────────
// Two simultaneous GETs for the same URL (with the same params) share one promise.
// Reduces duplicate network calls when multiple React Query observers mount at once.
const inflight = new Map<string, Promise<any>>();

function _dedupeKey(config: AxiosRequestConfig): string {
  const method = (config.method || "get").toLowerCase();
  const params = config.params ? JSON.stringify(config.params) : "";
  return `${method}:${config.url}:${params}`;
}

export const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,          // ← 15s default; per-call override via { timeout }
});

// Request interceptor — add auth + dedupe GETs
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — auto-refresh + fail-fast on timeouts
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.code === "ECONNABORTED" || !error.response) {
      return Promise.reject(error);
    }

    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem("refresh_token");
        if (refresh) {
          const res = await axios.post(
            `${API_URL}/api/v1/auth/refresh`,
            { refresh_token: refresh },
            { timeout: 5_000 }
          );
          const { access_token } = res.data;
          localStorage.setItem("access_token", access_token);
          original.headers.Authorization = `Bearer ${access_token}`;
          return api(original);
        }
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        if (typeof window !== "undefined") window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Wrap api.get to dedupe identical concurrent requests. Mutations (POST/PUT/PATCH/DELETE)
// are NOT deduped — each mutation must hit the server.
const _origGet = api.get.bind(api);
api.get = ((url: string, config?: AxiosRequestConfig) => {
  const merged: AxiosRequestConfig = { ...(config ?? {}), method: "get", url };
  const key = _dedupeKey(merged);
  const existing = inflight.get(key);
  if (existing) return existing;
  const p = _origGet(url, config).finally(() => {
    inflight.delete(key);
  });
  inflight.set(key, p);
  return p;
}) as typeof api.get;

// Convenience helper: wrap any promise with a hard timeout abort.
// Useful for non-axios async work (WebSocket handshake, file uploads, etc).
export function withTimeout<T>(promise: Promise<T>, ms: number, label = "request"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    promise.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}

export const WS_URL = API_URL.replace(/^http/, "ws");
