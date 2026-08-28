import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("bam_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.includes("/login")) {
      localStorage.removeItem("bam_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function apiError(e) {
  if (!e.response) {
    return "Tidak ada koneksi ke server. Periksa internet Anda lalu coba lagi.";
  }
  const detail = e.response?.data?.detail;
  if (detail == null) return e.message || "Terjadi kesalahan";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return String(detail);
}

export default api;
