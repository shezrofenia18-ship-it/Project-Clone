export function formatRupiah(n) {
  const num = Number(n || 0);
  return "Rp " + Math.round(num).toLocaleString("id-ID");
}

export function formatRupiahShort(n) {
  const num = Number(n || 0);
  if (Math.abs(num) >= 1000000) return "Rp " + (num / 1000000).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " jt";
  if (Math.abs(num) >= 1000) return "Rp " + (num / 1000).toLocaleString("id-ID", { maximumFractionDigits: 0 }) + " rb";
  return "Rp " + Math.round(num).toLocaleString("id-ID");
}

export function formatWeight(n, digits = 2) {
  const num = Number(n || 0);
  return num.toLocaleString("id-ID", { minimumFractionDigits: 0, maximumFractionDigits: digits }) + " kg";
}

export function formatNumber(n, digits = 0) {
  return Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: digits });
}

export function formatPct(n) {
  return Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 }) + "%";
}

export function parseDecimal(str) {
  if (typeof str === "number") return str;
  if (!str) return 0;
  return parseFloat(String(str).replace(/\./g, "").replace(",", ".")) || 0;
}

export function formatTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

export const CATEGORY_LABELS = {
  broiler: "Ayam Broiler",
  kampung: "Ayam Kampung",
  pejantan: "Ayam Pejantan",
  fillet: "Ayam Fillet",
  sampingan: "Produk Sampingan",
};

export const CUSTOMER_TYPES = {
  umum: "Umum",
  rumah_tangga: "Rumah Tangga",
  warung: "Warung",
  rumah_makan: "Rumah Makan",
  restoran: "Restoran",
  pedagang: "Pedagang",
  reseller: "Reseller",
};

export const PAYMENT_METHODS = ["cash", "transfer", "qris", "debit", "ewallet", "piutang"];
export const PAYMENT_LABELS = {
  cash: "Tunai", transfer: "Transfer", qris: "QRIS", debit: "Debit", ewallet: "E-Wallet", piutang: "Piutang",
};
