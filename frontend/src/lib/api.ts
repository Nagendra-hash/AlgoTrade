// Axios API client with timeout, interceptors and auto-refresh
// Path: frontend/src/lib/api.ts
import axios, { type AxiosInstance } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,          // ← 15s timeout prevents hanging requests
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    // Don't retry on timeout or network error — fail fast
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

export const WS_URL = API_URL.replace(/^http/, "ws");
