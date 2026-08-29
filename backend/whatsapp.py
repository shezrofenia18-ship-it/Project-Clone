"""Rekap tutup buku harian ke WhatsApp.

Dua mode, dipilih otomatis:

1. MODE OTOMATIS (butuh kredensial) — Meta WhatsApp Cloud API. Aktif hanya bila
   env `META_PHONE_NUMBER_ID` dan `META_ACCESS_TOKEN` terisi. Sesuai aturan Meta,
   pesan yang dimulai oleh bisnis di luar jendela 24 jam WAJIB memakai template
   yang sudah disetujui; karena itu ada env `WA_TEMPLATE_NAME`. Bila template
   belum dibuat, biarkan kosong -> sistem memakai pesan teks biasa yang hanya
   berhasil bila owner baru saja membalas chat (jendela 24 jam terbuka).

2. MODE 1-TAP (tanpa kredensial apa pun) — sistem menyiapkan teks rekap lengkap
   dan tautan wa.me, owner tinggal menekan sekali untuk mengirim. Dipakai sebagai
   fallback supaya rekap TIDAK PERNAH hilang diam-diam saat kredensial kosong
   atau saat provider menolak.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger("berkah.whatsapp")

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

PAYMENT_LABELS = {"cash": "Tunai", "transfer": "Transfer", "qris": "QRIS",
                  "debit": "Debit", "ewallet": "E-Wallet", "piutang": "Piutang"}


# ------------------------- format -------------------------
def rp(n) -> str:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        v = 0.0
    return "Rp " + f"{round(v):,}".replace(",", ".")


def num(n, digits=0) -> str:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{v:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def tanggal_panjang(iso: str) -> str:
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"
    except Exception:
        return iso or "-"


def normalize_number(raw: str) -> str:
    """Ubah 08xx / 8xx / +62xx / 62xx menjadi format 62xxxxxxxxx (tanpa +)."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""
    if digits.startswith("62"):
        return digits
    if digits.startswith("0"):
        return "62" + digits[1:]
    if digits.startswith("8"):
        return "62" + digits
    return digits


def e164(raw: str) -> str:
    n = normalize_number(raw)
    return f"+{n}" if n else ""


# ------------------------- isi pesan -------------------------
def build_closing_text(snap: Dict[str, Any], store: Dict[str, Any], notes: str = "") -> str:
    """Teks rekap siap kirim WhatsApp (memakai *tebal* gaya WhatsApp)."""
    nama = (store or {}).get("name") or "Berkah Ayam Mili"
    L: List[str] = []
    L.append(f"*REKAP TUTUP BUKU — {nama.upper()}*")
    L.append(tanggal_panjang(snap.get("date", "")))
    L.append("")
    L.append(f"*Omzet:* {rp(snap.get('omzet'))} ({num(snap.get('txn_count'))} transaksi)")
    L.append(f"HPP: {rp(snap.get('hpp'))}")
    L.append(f"*Laba kotor:* {rp(snap.get('gross_profit'))} (margin {num(snap.get('margin'), 2)}%)")
    L.append(f"Beban operasional: {rp(snap.get('opex'))}")
    L.append(f"*LABA BERSIH: {rp(snap.get('net_profit'))}*")

    methods = snap.get("by_method") or []
    L.append("")
    L.append("*UANG MASUK*")
    for m in methods:
        label = PAYMENT_LABELS.get(m.get("method"), m.get("method", "-"))
        L.append(f"• {label}: {rp(m.get('kas'))}")
    if snap.get("bayar_piutang_masuk"):
        L.append(f"• Pembayaran piutang: {rp(snap.get('bayar_piutang_masuk'))}")
    L.append(f"Total uang masuk: *{rp(snap.get('kas_masuk_total'))}*")
    if snap.get("piutang_baru"):
        L.append(f"Piutang baru hari ini: {rp(snap.get('piutang_baru'))}")

    L.append("")
    L.append("*TERJUAL*")
    L.append(f"• Berat: {num(snap.get('weight'), 2)} kg")
    L.append(f"• Ayam: {num(snap.get('ekor'))} ekor")
    if snap.get("pcs"):
        L.append(f"• Potongan: {num(snap.get('pcs'))} pcs")

    items = sorted(snap.get("stock_items") or [], key=lambda x: -float(x.get("value", 0) or 0))[:6]
    if items:
        L.append("")
        L.append("*STOK SISA*")
        for s in items:
            bagian = [f"{num(s.get('stock_kg'), 2)} kg"]
            if float(s.get("stock_ekor", 0) or 0):
                bagian.append(f"{num(s.get('stock_ekor'))} ekor")
            if float(s.get("stock_pcs", 0) or 0):
                bagian.append(f"{num(s.get('stock_pcs'))} pcs")
            L.append(f"• {s.get('name')}: {' · '.join(bagian)}")
    L.append(f"Nilai stok: *{rp(snap.get('stock_value'))}*")

    pur = snap.get("purchase") or {}
    if float(pur.get("total_modal", 0) or 0):
        L.append("")
        L.append(f"*Pembelian hari ini:* {rp(pur.get('total_modal'))} "
                 f"({num(pur.get('weight'), 2)} kg / {num(pur.get('ekor'))} ekor)")

    L.append("")
    L.append(f"Piutang belum lunas: {rp(snap.get('receivable_outstanding'))}")
    L.append(f"Hutang supplier: {rp(snap.get('payable_outstanding'))}")

    note = notes or snap.get("notes") or ""
    if note:
        L.append("")
        L.append(f"*Catatan:* {note}")

    L.append("")
    L.append("_Dikirim oleh sistem Berkah Ayam Mili_")
    return "\n".join(L)


def wa_me_link(number: str, text: str) -> str:
    n = normalize_number(number)
    encoded = quote(text)
    return f"https://wa.me/{n}?text={encoded}" if n else f"https://wa.me/?text={encoded}"


# ------------------------- Meta Cloud API -------------------------
def _cfg() -> Dict[str, str]:
    return {
        "phone_id": (os.environ.get("META_PHONE_NUMBER_ID") or "").strip(),
        "token": (os.environ.get("META_ACCESS_TOKEN") or "").strip(),
        "version": (os.environ.get("META_API_VERSION") or "v25.0").strip(),
        "template": (os.environ.get("WA_TEMPLATE_NAME") or "").strip(),
        "template_lang": (os.environ.get("WA_TEMPLATE_LANG") or "id").strip(),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["phone_id"] and c["token"])


def provider_info() -> Dict[str, Any]:
    c = _cfg()
    return {
        "configured": bool(c["phone_id"] and c["token"]),
        "provider": "meta_cloud_api",
        "template": c["template"] or None,
        "mode": ("template" if c["template"] else "freeform") if c["phone_id"] and c["token"] else "manual",
    }


async def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _cfg()
    url = f"https://graph.facebook.com/{c['version']}/{c['phone_id']}/messages"
    headers = {"Authorization": f"Bearer {c['token']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code >= 300:
        # Jangan pernah membocorkan token ke log/response.
        raise RuntimeError(f"WhatsApp provider {r.status_code}: {r.text[:300]}")
    return r.json()


async def send_text(to: str, text: str) -> Dict[str, Any]:
    """Pesan teks biasa. Hanya berhasil bila jendela 24 jam terbuka."""
    return await _post({
        "messaging_product": "whatsapp", "to": normalize_number(to),
        "type": "text", "text": {"preview_url": False, "body": text[:4000]},
    })


async def send_template(to: str, tanggal: str, omzet: str, transaksi: str) -> Dict[str, Any]:
    """Template yang sudah disetujui (3 parameter body: tanggal, omzet, transaksi)."""
    c = _cfg()
    return await _post({
        "messaging_product": "whatsapp", "to": normalize_number(to), "type": "template",
        "template": {
            "name": c["template"], "language": {"code": c["template_lang"]},
            "components": [{"type": "body", "parameters": [
                {"type": "text", "text": tanggal},
                {"type": "text", "text": omzet},
                {"type": "text", "text": str(transaksi)},
            ]}],
        },
    })


async def send_closing(snap: Dict[str, Any], store: Dict[str, Any], recipients: List[Dict[str, str]],
                       notes: str = "") -> Dict[str, Any]:
    """Kirim rekap ke semua penerima.

    Selalu mengembalikan hasil per penerima + tautan 1-tap sebagai cadangan,
    dan TIDAK PERNAH melempar exception supaya proses tutup buku tetap sukses.
    """
    text = build_closing_text(snap, store, notes)
    results = []
    configured = is_configured()
    for rec in recipients:
        number = normalize_number(rec.get("number"))
        if not number:
            continue
        item = {"name": rec.get("name") or number, "number": number,
                "link": wa_me_link(number, text), "sent": False, "error": None}
        if configured:
            try:
                c = _cfg()
                if c["template"]:
                    res = await send_template(number, tanggal_panjang(snap.get("date", "")),
                                              rp(snap.get("omzet")), num(snap.get("txn_count")))
                else:
                    res = await send_text(number, text)
                item["sent"] = True
                item["message_id"] = (res.get("messages") or [{}])[0].get("id")
            except Exception as e:
                item["error"] = str(e)[:300]
                logger.warning("Kirim WhatsApp ke %s gagal: %s", number[:6] + "***", item["error"])
        results.append(item)

    sent_count = sum(1 for r in results if r["sent"])
    return {
        "text": text,
        "provider": provider_info(),
        "results": results,
        "sent_count": sent_count,
        # manual = owner perlu menekan tautan wa.me sekali
        "mode": "auto" if (configured and sent_count) else "manual",
    }
