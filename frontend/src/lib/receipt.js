import { formatRupiah, formatQtyUnit, formatTime, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { toast } from "sonner";
import { devWarn } from "@/lib/log";

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

// Lebar kertas struk printer termal kasir (mm). Area cetak efektif 58mm = ~48mm,
// tapi mayoritas driver 58mm menerima 58mm dengan margin 0 lalu memusatkan sendiri.
export const RECEIPT_PAPER_MM = 58;

// HTML struk siap cetak untuk printer TERMAL 58mm.
// Kunci agar tidak terpotong / melebar:
//   - @page { size: 58mm auto; margin: 0 }  -> printer tahu lebar & panjang mengalir
//   - body width 58mm dengan padding kecil, font monospace 11px
//   - ruang kosong di bawah supaya struk mudah disobek
export function receiptHtml(sale, store) {
  const s = normStore(store);
  const rows = sale.items.map((it) => {
    const x = line(it);
    return `<div class="it"><div class="nm">${esc(x.name)}</div><div class="rw"><span>${esc(x.detail)}</span><span>${x.sub}</span></div></div>`;
  }).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Struk</title>
  <style>
    @page { size: ${RECEIPT_PAPER_MM}mm auto; margin: 0; }
    * { font-family: 'Courier New', 'Consolas', monospace; box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: #fff; }
    body {
      width: ${RECEIPT_PAPER_MM}mm;
      padding: 2mm 2mm 10mm;
      color: #000;
      font-size: 11px;
      line-height: 1.35;
      -webkit-print-color-adjust: exact;
    }
    .c { text-align: center; }
    .hr { border-top: 1px dashed #000; margin: 1.5mm 0; }
    .rw { display: flex; justify-content: space-between; gap: 2mm; }
    .rw span:last-child { white-space: nowrap; }
    .it { margin-bottom: 1mm; }
    .nm { font-weight: bold; word-break: break-word; }
    .tot { font-size: 13px; font-weight: bold; }
    h1 { font-size: 14px; margin: 0; line-height: 1.2; word-break: break-word; }
    small { font-size: 9px; display: block; word-break: break-word; }
    .promo { border: 1px dashed #000; padding: 1.5mm; margin-top: 2mm; text-align: center;
             font-size: 9px; font-weight: bold; line-height: 1.3; }
    .promo em { display: block; font-weight: normal; font-style: normal; font-size: 8px; margin-top: 0.5mm; }
    @media print { body { width: ${RECEIPT_PAPER_MM}mm; } }
  </style></head><body>
    <div class="c"><h1>${esc(s.name)}</h1><small>${esc(s.tagline)}</small>
    ${s.address ? `<small>${esc(s.address)}</small>` : ""}
    ${s.phone ? `<small>Telp/WA: ${esc(s.phone)}</small>` : ""}
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
  </body></html>`;
}

// Cetak lewat iframe tersembunyi: tidak kena pemblokir popup, jadi bisa dipakai
// untuk cetak OTOMATIS setelah transaksi. Kalau gagal, jatuh ke jendela baru.
function printViaIframe(html) {
  const frame = document.createElement("iframe");
  frame.setAttribute("title", "struk");
  frame.setAttribute("aria-hidden", "true");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  document.body.appendChild(frame);
  const win = frame.contentWindow;
  if (!win) {
    frame.remove();
    return false;
  }
  const doc = win.document;
  doc.open();
  doc.write(html);
  doc.close();
  let removed = false;
  const cleanup = () => {
    if (removed) return;
    removed = true;
    setTimeout(() => frame.remove(), 500);
  };
  win.onafterprint = cleanup;
  // beri jeda singkat supaya isi struk selesai dirender sebelum dialog cetak muncul
  setTimeout(() => {
    try {
      win.focus();
      win.print();
    } catch (err) {
      // dialog cetak ditolak browser -> beri tahu kasir, jangan gagal diam-diam
      devWarn("receipt.print", err);
      toast.error("Cetak struk gagal — silakan tekan tombol Cetak lagi");
      cleanup();
      return;
    }
    // jaring pengaman bila browser tidak mengirim event afterprint
    setTimeout(cleanup, 60000);
  }, 250);
  return true;
}

function printViaWindow(html) {
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank", "width=340,height=640");
  if (!w) {
    URL.revokeObjectURL(url);
    toast.error("Popup diblokir — izinkan popup untuk mencetak struk");
    return false;
  }
  w.addEventListener("load", () => {
    w.focus();
    w.print();
  });
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  return true;
}

export function printReceipt(sale, store) {
  if (!sale) return false;
  const html = receiptHtml(sale, store);
  try {
    if (printViaIframe(html)) return true;
  } catch (e) {
    // Iframe gagal (mis. browser membatasi document.write) -> catat lalu coba jendela baru.
    devWarn("receipt.printViaIframe", e);
  }
  return printViaWindow(html);
}

// Struk contoh untuk tombol "Tes Cetak" di Pengaturan.
export function sampleSale() {
  return {
    id: "TES", created_at: new Date().toISOString(),
    cashier_name: "Tes Printer", customer_name: "Umum",
    items: [
      { name: "Ayam Broiler (contoh)", unit: "kg", qty: 1.25, price: 36000, subtotal: 45000 },
      { name: "Ayam Fillet (contoh)", unit: "kg", qty: 0.5, price: 70000, subtotal: 35000 },
      { name: "Ceker Ayam (contoh)", unit: "pcs", qty: 3, price: 2000, subtotal: 6000 },
    ],
    total: 86000, paid: 100000, change: 14000, receivable: 0,
    payment_method: "cash",
  };
}

