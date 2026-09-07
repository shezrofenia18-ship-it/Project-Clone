// Helper URL gambar (foto produk & bukti pengeluaran).
//
// Gambar TIDAK lagi dimuat langsung dari domain publik Cloudflare R2 (pub-*.r2.dev)
// karena domain itu diblokir sebagian ISP Indonesia (Internet Positif). Backend
// menyediakan IMAGE PROXY: GET {BACKEND}/api/images/<key> yang mengambil objek dari R2
// dan meneruskannya dengan Content-Type yang tepat. Yang tersimpan di database adalah
// path relatif "/api/images/<key>"; helper ini menempelkan domain backend.
export const IMAGE_PROXY_PREFIX = "/api/images/";
const APP_KEY_PREFIX = "berkah-ayam-mili/";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");

// URL R2 lama yang mungkin masih tersimpan/ter-cache di klien.
const R2_LEGACY_RE = /^https?:\/\/[^/]+\.(?:r2\.dev|r2\.cloudflarestorage\.com)\/(.+)$/i;

/**
 * Rapikan URL gambar sebelum dipasang ke <img src>.
 *  - "/api/images/<key>" (bentuk baru, relatif) -> BACKEND_URL + path.
 *  - URL absolut yang mengandung "/api/images/" atau "/api/files/" -> dipetakan ke
 *    BACKEND_URL saat ini (domain backend boleh berganti).
 *  - URL R2 lama "https://pub-xxx.r2.dev/berkah-ayam-mili/..." -> lewat proxy backend.
 *  - URL ganda hasil frontend lama ("https://backend/https://pub-xxx...") disembuhkan.
 *  - URL eksternal lain (mis. gambar contoh), data:, blob: dibiarkan.
 */
export function resolveImageUrl(url) {
  let s = String(url || "").trim();
  if (!s) return "";
  let low = s.toLowerCase();
  if (low.startsWith("data:") || low.startsWith("blob:")) return s;

  // 1) URL ganda -> ambil URL absolut terakhir
  const idx = Math.max(low.lastIndexOf("https://"), low.lastIndexOf("http://"));
  if (idx > 0) { s = s.slice(idx); low = s.toLowerCase(); }

  // 2) Sudah menunjuk proxy/tautan backend -> pakai domain backend saat ini
  for (const marker of [IMAGE_PROXY_PREFIX, "/api/files/"]) {
    const i = low.indexOf(marker);
    if (i >= 0) return `${BACKEND_URL}${s.slice(i)}`;
  }

  // 3) URL R2 lama -> proxy backend
  const m = s.match(R2_LEGACY_RE);
  if (m) {
    let key = m[1].split("?")[0].split("#")[0];
    // bentuk endpoint S3: https://<acct>.r2.cloudflarestorage.com/<bucket>/<key>
    const p = key.indexOf(APP_KEY_PREFIX);
    if (p > 0) key = key.slice(p);
    if (key.startsWith(APP_KEY_PREFIX)) return `${BACKEND_URL}${IMAGE_PROXY_PREFIX}${key}`;
  }

  // 4) Path relatif lain -> domain backend; URL eksternal apa adanya
  if (s.startsWith("/")) return `${BACKEND_URL}${s}`;
  return s;
}

/** Apakah URL ini dilayani lewat proxy gambar backend? */
export function isProxiedImage(url) {
  return resolveImageUrl(url).includes(IMAGE_PROXY_PREFIX);
}
