import axios from "axios";

const DEFAULT_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const getApiKey = () => localStorage.getItem("psx_api_key") || "";
export const setApiKey = (k) => localStorage.setItem("psx_api_key", k);
export const getBaseUrl = () => localStorage.getItem("psx_api_base") || DEFAULT_BASE;
export const setBaseUrl = (u) => localStorage.setItem("psx_api_base", u || DEFAULT_BASE);

const client = axios.create({ timeout: 60000 });

client.interceptors.request.use((cfg) => {
  cfg.baseURL = getBaseUrl();
  const key = getApiKey();
  if (key) cfg.headers["X-API-Key"] = key;
  return cfg;
});

export const api = {
  health: () => client.get("/health").then((r) => r.data),
  signal: () => client.get("/signal").then((r) => r.data),
  opportunities: (limit = 100) =>
    client.get(`/opportunities?limit=${limit}`).then((r) => r.data),
  stock: (ticker) =>
    client.get(`/stock/${encodeURIComponent(ticker)}`).then((r) => r.data),
  query: (question) => client.post("/query", { question }).then((r) => r.data),
};

// Turn any axios failure into a human-readable, non-crashing message.
export function apiErrorMessage(err) {
  if (err?.response?.data?.detail) {
    const d = err.response.data.detail;
    return typeof d === "string" ? d : JSON.stringify(d);
  }
  if (err?.response) return `Request failed (HTTP ${err.response.status}).`;
  if (err?.request)
    return "Cannot reach the API. Is the backend running, and is the base URL / API key correct?";
  return err?.message || "Unknown error.";
}
