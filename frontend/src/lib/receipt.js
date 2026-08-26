import { formatRupiah, formatWeight, formatTime, formatDate, PAYMENT_LABELS } from "@/lib/format";

const STORE = "Berkah Ayam Mili";

function line(it) {
  const q = it.unit === "kg" ? formatWeight(it.qty, 3) : `${it.qty} ekor`;
  return { name: it.name, detail: `${q} x ${formatRupiah(it.price)}`, sub: formatRupiah(it.subtotal) };
}

export function receiptText(sale, store = STORE) {
  const L = [];
  L.push(`*${store}*`);
  L.push("Ayam Potong & Fillet");
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
  return L.join("\n");
}

export function waShareReceipt(sale, store = STORE, phone) {
  const text = encodeURIComponent(receiptText(sale, store));
  let num = String(phone || "").replace(/[^0-9]/g, "");
  if (num.startsWith("0")) num = "62" + num.slice(1);
  const url = num ? `https://wa.me/${num}?text=${text}` : `https://wa.me/?text=${text}`;
  window.open(url, "_blank");
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function printReceipt(sale, store = STORE) {
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
  </style></head><body>
    <div class="c"><h1>${esc(store)}</h1><small>Ayam Potong &amp; Fillet</small></div>
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
  </body></html>`;
  const w = window.open("", "_blank", "width=340,height=640");
  if (!w) return;
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => { w.print(); }, 350);
}
