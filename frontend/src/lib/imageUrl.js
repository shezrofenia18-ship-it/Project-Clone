// Helper URL gambar (foto produk & bukti pengeluaran) yang disimpan di Cloudflare R2.
//
// Domain publik R2 yang di-whitelist untuk dirender <img>. Nilai ini juga dipakai
// di header Content-Security-Policy (public/index.html & vercel.json).
export const R2_PUBLIC_HOSTS = [
  "pub-a275aff5ab9848b3931596d2654b12e7.r2.dev",
];

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");

/**
 * Rapikan URL gambar sebelum dipasang ke <img src>.
 *  - URL absolut (https://pub-xxx.r2.dev/...) dipakai apa adanya.
 *  - URL ganda hasil frontend lama ("https://backend/https://pub-xxx.r2.dev/...")
 *    disembuhkan dengan mengambil URL absolut TERAKHIR di dalam teks.
 *  - URL relatif lama ("/api/files/<id>") diberi awalan domain backend.
 *  - data:/blob: (pratinjau lokal) dibiarkan.
 */
export function resolveImageUrl(url) {
  const s = String(url || "").trim();
  if (!s) return "";
  const low = s.toLowerCase();
  if (low.startsWith("data:") || low.startsWith("blob:")) return s;
  const idx = Math.max(low.lastIndexOf("https://"), low.lastIndexOf("http://"));
  if (idx > 0) return s.slice(idx);
  if (idx === 0) return s;
  if (s.startsWith("/")) return `${BACKEND_URL}${s}`;
  return s;
}

/** Apakah URL ini berasal dari domain R2 publik yang di-whitelist? */
export function isR2Url(url) {
  try {
    const host = new URL(resolveImageUrl(url)).host;
    return R2_PUBLIC_HOSTS.includes(host) || host.endsWith(".r2.dev");
  } catch {
    return false;
  }
}
