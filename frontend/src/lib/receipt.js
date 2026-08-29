import { formatRupiah, formatQtyUnit, formatTime, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { toast } from "sonner";

const DEFAULT_STORE = { name: "Berkah Ayam Mili", tagline: "Ayam Potong & Fillet", address: "", phone: "" };

// Peringatan wajib di struk (permintaan owner). Disimpan di satu tempat supaya
// pratinjau di layar, struk cetak, dan teks WhatsApp selalu sama.
export const RECEIPT_PROMO = "Belanja GRATIS jika kasir tidak menyerahkan struk pembayaran";
export const RECEIPT_PROMO_NOTE = "*syarat & ketentuan berlaku*";

// Menerima objek toko {name, tagline, address, phone} maupun string nama toko.
export function normStore(store) {
  if (!store) return DEFAULT_STORE;
  if (typeof store === "string") return { ...DEFAULT_STORE, name: store };
  return {
    name: store.name || DEFAULT_STORE.name,
    tagline: store.tagline || DEFAULT_STORE.tagline,
    address: store.address || "",
    phone: store.phone || "",
  };
}

function line(it) {
  const q = formatQtyUnit(it.qty, it.unit, 3);
  return { name: it.name, detail: `${q} x ${formatRupiah(it.price)}`, sub: formatRupiah(it.subtotal) };
}

export function receiptText(sale, store) {
  const s = normStore(store);
  const L = [];
  L.push(`*${s.name}*`);
  L.push(s.tagline);
  if (s.address) L.push(s.address);
  if (s.phone) L.push(`Telp/WA: ${s.phone}`);
  L.push("----------------------------");
  L.push(`${formatDate(sale.created_at)} ${formatTime(sale.created_at)}`);
  L.push(`Kasir   : ${sale.cashier_name}`);
  L.push(`Pembeli : ${sale.customer_name}`);
  L.push("----------------------------");
  sale.items.forEach((it) => {
    const x = line(it);
    L.push(x.name);
    L.push(`  ${x.detail} = ${x.sub}`);
  });
  L.push("----------------------------");
  L.push(`TOTAL   : ${formatRupiah(sale.total)}`);
  L.push(`Bayar (${PAYMENT_LABELS[sale.payment_method] || sale.payment_method}): ${formatRupiah(sale.paid)}`);
  if (sale.change > 0) L.push(`Kembali : ${formatRupiah(sale.change)}`);
  if (sale.receivable > 0) L.push(`Piutang : ${formatRupiah(sale.receivable)}`);
  L.push("----------------------------");
  L.push("Terima kasih atas kunjungan Anda");
  L.push("");
  L.push(RECEIPT_PROMO);
  L.push(RECEIPT_PROMO_NOTE);
  return L.join("\n");
}

export function waShareReceipt(sale, store, phone) {
  const text = encodeURIComponent(receiptText(sale, store));
  let num = String(phone || "").replace(/[^0-9]/g, "");
  if (num.startsWith("0")) num = "62" + num.slice(1);
  const url = num ? `https://wa.me/${num}?text=${text}` : `https://wa.me/?text=${text}`;
  window.open(url, "_blank");
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function printReceipt(sale, store) {
  const s = normStore(store);
  const rows = sale.items.map((it) => {
    const x = line(it);
    return `<div class="it"><div class="nm">${esc(x.name)}</div><div class="rw"><span>${esc(x.detail)}</span><span>${x.sub}</span></div></div>`;
  }).join("");
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Struk</title>
  <style>
    *{font-family:'Courier New',monospace;box-sizing:border-box}
    body{width:280px;margin:0 auto;padding:10px;color:#000}
    .c{text-align:center}.b{font-weight:bold}
    .hr{border-top:1px dashed #000;margin:6px 0}
    .rw{display:flex;justify-content:space-between;font-size:12px}
    .it{margin-bottom:4px}.nm{font-size:12px}
    .tot{font-size:14px;font-weight:bold}
    h1{font-size:16px;margin:0}
    small{font-size:10px}
    .promo{border:1px dashed #000;padding:5px;margin-top:6px;text-align:center;font-size:10px;font-weight:bold;line-height:1.35}
    .promo em{display:block;font-weight:normal;font-style:normal;font-size:9px;margin-top:2px}
  </style></head><body>
    <div class="c"><h1>${esc(s.name)}</h1><small>${esc(s.tagline)}</small>
    ${s.address ? `<div><small>${esc(s.address)}</small></div>` : ""}
    ${s.phone ? `<div><small>Telp/WA: ${esc(s.phone)}</small></div>` : ""}
    </div>
    <div class="hr"></div>
    <div class="rw"><span>${formatDate(sale.created_at)}</span><span>${formatTime(sale.created_at)}</span></div>
    <div class="rw"><span>Kasir</span><span>${esc(sale.cashier_name)}</span></div>
    <div class="rw"><span>Pembeli</span><span>${esc(sale.customer_name)}</span></div>
    <div class="hr"></div>
    ${rows}
    <div class="hr"></div>
    <div class="rw tot"><span>TOTAL</span><span>${formatRupiah(sale.total)}</span></div>
    <div class="rw"><span>Bayar (${esc(PAYMENT_LABELS[sale.payment_method] || sale.payment_method)})</span><span>${formatRupiah(sale.paid)}</span></div>
    ${sale.change > 0 ? `<div class="rw"><span>Kembali</span><span>${formatRupiah(sale.change)}</span></div>` : ""}
    ${sale.receivable > 0 ? `<div class="rw"><span>Piutang</span><span>${formatRupiah(sale.receivable)}</span></div>` : ""}
    <div class="hr"></div>
    <div class="c"><small>Terima kasih atas kunjungan Anda</small></div>
    <div class="promo">${esc(RECEIPT_PROMO)}<em>${esc(RECEIPT_PROMO_NOTE)}</em></div>
    <script>window.onload=function(){window.focus();window.print();};<\/script>
  </body></html>`;
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank", "width=340,height=640");
  if (!w) {
    URL.revokeObjectURL(url);
    toast.error("Popup diblokir — izinkan popup untuk mencetak struk");
    return;
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
