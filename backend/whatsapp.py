"""Rekap tutup buku harian ke WhatsApp.

Dua mode, dipilih otomatis:

1. MODE OTOMATIS (butuh kredensial) — Meta WhatsApp Cloud API, Graph API v26.0.
   Aktif hanya bila env `META_PHONE_NUMBER_ID` dan `META_ACCESS_TOKEN` terisi.
   Sesuai aturan Meta, pesan yang DIMULAI OLEH BISNIS di luar jendela 24 jam
   (rekap malam otomatis) WAJIB memakai template yang sudah disetujui. Template
   rekap ringkas (tanggal, omzet, laba bersih, jumlah transaksi) didefinisikan di
   modul ini (`TEMPLATE_BODY`) dan bisa disubmit ke Meta lewat `create_template()`.
   Bila template belum disetujui, sistem otomatis mencoba teks biasa (berhasil
   hanya bila owner baru membalas chat), lalu jatuh ke mode 1-tap.

2. MODE 1-TAP (tanpa kredensial apa pun) — sistem menyiapkan teks rekap lengkap
   dan tautan wa.me, owner tinggal menekan sekali untuk mengirim. Dipakai sebagai
   fallback supaya rekap TIDAK PERNAH hilang diam-diam saat kredensial kosong
   atau saat provider menolak.
"""

import asyncio
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
def build_closing_text(snap: Dict[str, Any], store: Dict[str, Any], notes: str = "",
                       pdf_url: str = "") -> str:
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

    if pdf_url:
        L.append("")
        L.append("*PDF Laporan Penjualan:*")
        L.append(pdf_url)

    L.append("")
    L.append("_Dikirim oleh sistem Berkah Ayam Mili_")
    return "\n".join(L)


def wa_me_link(number: str, text: str) -> str:
    n = normalize_number(number)
    encoded = quote(text)
    return f"https://wa.me/{n}?text={encoded}" if n else f"https://wa.me/?text={encoded}"


# ------------------------- Meta Cloud API -------------------------
# Versi Graph API di-PIN (bukan dibiarkan "terbaru") supaya perubahan di sisi Meta
# tidak diam-diam mengubah perilaku pengiriman di produksi.
DEFAULT_API_VERSION = "v26.0"
DEFAULT_TEMPLATE_NAME = "rekap_tutup_buku_harian"
# Template TERPISAH untuk versi berlampiran PDF: template body-only TIDAK BISA
# diberi header dokumen saat pengiriman, jadi header DOCUMENT harus ikut saat
# template dibuat & disetujui.
DEFAULT_TEMPLATE_DOC_NAME = "rekap_tutup_buku_pdf"
DEFAULT_TEMPLATE_LANG = "id"
MAX_PDF_BYTES = 95 * 1024 * 1024  # batas dokumen Cloud API 100 MB, disisakan margin

# ---- Template UTILITY siap-submit ke Meta -------------------------------------
# Pesan yang DIMULAI OLEH BISNIS (rekap malam otomatis) hanya boleh memakai
# template yang sudah disetujui Meta. Karena itu templatenya dibuat RINGKAS
# (4 parameter); rincian penuh + PDF tetap ada di dalam aplikasi.
TEMPLATE_PARAMS = ["tanggal", "omzet", "laba_bersih", "jumlah_transaksi"]
TEMPLATE_BODY = (
    "Rekap tutup buku {{tanggal}}.\n"
    "Omzet {{omzet}}, laba bersih {{laba_bersih}}, {{jumlah_transaksi}} transaksi.\n"
    "Rincian lengkap dan PDF tersedia di aplikasi."
)
TEMPLATE_EXAMPLE = {
    "tanggal": "29 Agustus 2026",
    "omzet": "Rp 3.743.030",
    "laba_bersih": "Rp 444.000",
    "jumlah_transaksi": "14",
}

# Kode error Meta yang TIDAK boleh di-retry (retry hanya memperburuk / sia-sia).
PERMANENT_CODES = {0, 3, 190, 200, 131026, 131047, 131051, 132000, 132001,
                   132005, 132007, 132012, 132015, 132016, 133010}
# Kode error transient: aman di-retry dengan backoff.
TRANSIENT_CODES = {130429, 131056, 131000, 368}

# Penjelasan berbahasa Indonesia supaya owner tahu harus berbuat apa.
ERROR_HINTS = {
    131026: "Nomor tujuan tidak bisa menerima pesan (bukan nomor WhatsApp, "
            "salah format, atau memblokir bisnis). Periksa nomor penerima.",
    132000: "Jumlah parameter tidak cocok dengan template yang disetujui Meta. "
            "Buat ulang template lewat tombol di Pengaturan.",
    132001: "Template atau bahasanya tidak ditemukan di akun WhatsApp Business. "
            "Pastikan nama template sama persis dan sudah DISETUJUI.",
    132015: "Template dihentikan sementara oleh Meta karena kualitas rendah.",
    132016: "Template dinonaktifkan permanen oleh Meta. Buat template baru.",
    130429: "Batas kecepatan kirim tercapai. Sistem akan mencoba lagi otomatis.",
    131056: "Terlalu banyak pesan ke nomor yang sama dalam waktu singkat.",
    190: "Access token tidak valid atau kedaluwarsa. Buat token System User baru.",
    0: "Token/izin bermasalah. Pastikan System User punya akses App + WABA.",
}


class WaError(RuntimeError):
    """Error provider WhatsApp yang sudah diklasifikasi (retryable atau tidak)."""

    def __init__(self, message: str, code=None, subcode=None, fbtrace=None,
                 status=None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.subcode = subcode
        self.fbtrace = fbtrace
        self.status = status
        self.retryable = retryable

    @property
    def hint(self) -> str:
        return ERROR_HINTS.get(self.code, "")

    def as_dict(self) -> Dict[str, Any]:
        return {"message": str(self)[:300], "code": self.code, "subcode": self.subcode,
                "fbtrace_id": self.fbtrace, "http_status": self.status,
                "retryable": self.retryable, "hint": self.hint}


def _cfg() -> Dict[str, str]:
    return {
        "phone_id": (os.environ.get("META_PHONE_NUMBER_ID") or "").strip(),
        "token": (os.environ.get("META_ACCESS_TOKEN") or "").strip(),
        "waba_id": (os.environ.get("META_WABA_ID") or "").strip(),
        # hanya dipakai untuk mengunggah CONTOH PDF saat membuat template berheader
        "app_id": (os.environ.get("META_APP_ID") or "").strip(),
        "version": (os.environ.get("META_API_VERSION") or DEFAULT_API_VERSION).strip(),
        "template": (os.environ.get("WA_TEMPLATE_NAME") or DEFAULT_TEMPLATE_NAME).strip(),
        "template_doc": (os.environ.get("WA_TEMPLATE_DOC_NAME") or DEFAULT_TEMPLATE_DOC_NAME).strip(),
        "template_lang": (os.environ.get("WA_TEMPLATE_LANG") or DEFAULT_TEMPLATE_LANG).strip(),
        # "named" (disarankan) atau "positional" ({{1}}..{{4}})
        "param_format": (os.environ.get("WA_TEMPLATE_PARAM_FORMAT") or "named").strip().lower(),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["phone_id"] and c["token"])


def provider_info() -> Dict[str, Any]:
    c = _cfg()
    ok = bool(c["phone_id"] and c["token"])
    return {
        "configured": ok,
        "provider": "meta_cloud_api",
        "api_version": c["version"],
        "template": c["template"],
        "template_doc": c["template_doc"],
        "template_lang": c["template_lang"],
        "param_format": c["param_format"],
        "waba_configured": bool(c["waba_id"]),
        "app_configured": bool(c["app_id"]),
        # template = kirim otomatis penuh; manual = owner tekan tautan wa.me
        "mode": "template" if ok else "manual",
        "missing": [k for k, v in (("META_PHONE_NUMBER_ID", c["phone_id"]),
                                   ("META_ACCESS_TOKEN", c["token"]),
                                   ("META_WABA_ID", c["waba_id"]),
                                   ("META_APP_ID", c["app_id"])) if not v],
    }


def template_spec(with_document: bool = False) -> Dict[str, Any]:
    """Spesifikasi template siap dipakai owner untuk submit ke Meta (atau dicopy)."""
    c = _cfg()
    return {
        "name": c["template_doc"] if with_document else c["template"],
        "language": c["template_lang"],
        "category": "UTILITY",
        "parameter_format": c["param_format"].upper(),
        "with_document": with_document,
        "header": "DOCUMENT (PDF Laporan Penjualan)" if with_document else None,
        "body": TEMPLATE_BODY,
        "params": TEMPLATE_PARAMS,
        "example": TEMPLATE_EXAMPLE,
        "payload": _template_create_payload(with_document=with_document,
                                            header_handle="<handle-contoh-pdf>" if with_document else None),
    }


def _template_create_payload(with_document: bool = False,
                             header_handle: Optional[str] = None) -> Dict[str, Any]:
    c = _cfg()
    named = c["param_format"] != "positional"
    if named:
        body_text = TEMPLATE_BODY
        example = {"body_text_named_params": [
            {"param_name": p, "example": TEMPLATE_EXAMPLE[p]} for p in TEMPLATE_PARAMS]}
    else:
        body_text = TEMPLATE_BODY
        for idx, p in enumerate(TEMPLATE_PARAMS, start=1):
            body_text = body_text.replace("{{" + p + "}}", "{{" + str(idx) + "}}")
        example = {"body_text": [[TEMPLATE_EXAMPLE[p] for p in TEMPLATE_PARAMS]]}
    components: List[Dict[str, Any]] = []
    if with_document:
        # Meta mewajibkan contoh media (asset handle) untuk header DOCUMENT.
        components.append({"type": "HEADER", "format": "DOCUMENT",
                           "example": {"header_handle": [header_handle or ""]}})
    components.append({"type": "BODY", "text": body_text, "example": example})
    return {
        "name": c["template_doc"] if with_document else c["template"],
        "language": c["template_lang"],
        "category": "UTILITY",
        "parameter_format": "NAMED" if named else "POSITIONAL",
        "components": components,
    }


def _parse_error(status: int, body: str) -> WaError:
    """Ubah respons error Meta menjadi WaError. Token TIDAK pernah ikut tercatat."""
    code = subcode = fbtrace = None
    msg = body[:300]
    try:
        import json
        err = (json.loads(body) or {}).get("error") or {}
        code = err.get("code")
        subcode = err.get("error_subcode")
        fbtrace = err.get("fbtrace_id")
        msg = err.get("error_user_msg") or err.get("message") or msg
    except Exception:
        pass
    retryable = bool(code in TRANSIENT_CODES or (status >= 500 and code not in PERMANENT_CODES))
    return WaError(f"WhatsApp {status}: {msg}", code=code, subcode=subcode,
                   fbtrace=fbtrace, status=status, retryable=retryable)


async def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
                   params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Dict[str, Any]:
    """Panggil Graph API dengan retry-backoff HANYA untuk error transient."""
    c = _cfg()
    if not c["token"]:
        raise WaError("Kredensial WhatsApp belum diisi", code=None, retryable=False)
    url = f"https://graph.facebook.com/{c['version']}/{path}"
    headers = {"Authorization": f"Bearer {c['token']}", "Content-Type": "application/json"}
    delay = 1.5
    last: Optional[WaError] = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r = await client.request(method, url, headers=headers, json=payload, params=params)
        except httpx.HTTPError as e:
            last = WaError(f"Meta tidak dapat dihubungi: {e}", retryable=True)
        else:
            if r.status_code < 300:
                try:
                    return r.json()
                except ValueError:
                    return {"raw": r.text[:300]}
            last = _parse_error(r.status_code, r.text)
        if not last.retryable or attempt >= retries:
            raise last
        logger.warning("Retry WhatsApp (%s) percobaan %s: %s", path.split("/")[-1],
                       attempt + 1, str(last)[:160])
        await asyncio.sleep(delay)
        delay *= 2.5
    raise last  # pragma: no cover


async def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await _request("POST", f"{_cfg()['phone_id']}/messages", payload)


# ------------------------- Media (lampiran PDF) -------------------------
async def upload_media_pdf(pdf: bytes, filename: str = "laporan-penjualan.pdf") -> str:
    """Unggah PDF ke Cloud API -> media ID (berlaku 30 hari, bisa dipakai
    berulang untuk beberapa penerima). Dipakai untuk header dokumen template
    sehingga TIDAK perlu URL publik."""
    c = _cfg()
    if not (c["phone_id"] and c["token"]):
        raise WaError("Kredensial WhatsApp belum diisi", retryable=False)
    if not pdf:
        raise WaError("PDF kosong", retryable=False)
    if len(pdf) > MAX_PDF_BYTES:
        raise WaError(f"PDF terlalu besar ({len(pdf) // 1048576} MB, batas 100 MB)",
                      retryable=False)
    url = f"https://graph.facebook.com/{c['version']}/{c['phone_id']}/media"
    headers = {"Authorization": f"Bearer {c['token']}"}
    files = {"file": (filename, pdf, "application/pdf")}
    data = {"messaging_product": "whatsapp", "type": "application/pdf"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, data=data, files=files)
    except httpx.HTTPError as e:
        raise WaError(f"Gagal mengunggah PDF: {e}", retryable=True)
    if r.status_code >= 300:
        raise _parse_error(r.status_code, r.text)
    mid = (r.json() or {}).get("id")
    if not mid:
        raise WaError("Meta tidak mengembalikan media ID", retryable=False)
    return mid


async def upload_sample_handle(pdf: bytes, filename: str = "contoh-laporan.pdf") -> str:
    """Resumable Upload API -> asset handle `h` untuk CONTOH media saat membuat
    template berheader DOCUMENT. Butuh META_APP_ID; memakai skema Authorization
    'OAuth' sesuai dokumentasi Graph API upload."""
    c = _cfg()
    if not c["app_id"]:
        raise WaError("META_APP_ID belum diisi di backend/.env — dibutuhkan hanya untuk "
                      "mengunggah contoh PDF saat membuat template berlampiran", retryable=False)
    base = f"https://graph.facebook.com/{c['version']}"
    headers = {"Authorization": f"OAuth {c['token']}"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r1 = await client.post(f"{base}/{c['app_id']}/uploads", headers=headers,
                                   data={"file_name": filename, "file_length": str(len(pdf)),
                                         "file_type": "application/pdf"})
            if r1.status_code >= 300:
                raise _parse_error(r1.status_code, r1.text)
            session = (r1.json() or {}).get("id")
            if not session:
                raise WaError("Sesi upload contoh PDF tidak terbentuk", retryable=False)
            r2 = await client.post(f"{base}/{session}",
                                   headers={**headers, "file_offset": "0"}, content=pdf)
            if r2.status_code >= 300:
                raise _parse_error(r2.status_code, r2.text)
            handle = (r2.json() or {}).get("h")
    except httpx.HTTPError as e:
        raise WaError(f"Gagal mengunggah contoh PDF: {e}", retryable=True)
    if not handle:
        raise WaError("Meta tidak mengembalikan handle contoh PDF", retryable=False)
    return handle


async def send_text(to: str, text: str) -> Dict[str, Any]:
    """Pesan teks biasa. Hanya berhasil bila jendela 24 jam terbuka."""
    return await _post({
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": normalize_number(to),
        "type": "text", "text": {"preview_url": False, "body": text[:4000]},
    })


async def send_template(to: str, values: Dict[str, str], media_id: Optional[str] = None,
                        filename: str = "laporan-penjualan.pdf") -> Dict[str, Any]:
    """Kirim template yang sudah disetujui. Mendukung named & positional.

    Bila `media_id` diberikan, dipakai template BERLAMPIRAN (header DOCUMENT).
    Catatan Meta: header dokumen template tidak menerima `caption`.
    """
    c = _cfg()
    named = c["param_format"] != "positional"
    parameters = []
    for p in TEMPLATE_PARAMS:
        item = {"type": "text", "text": str(values.get(p, "-"))}
        if named:
            item["parameter_name"] = p  # wajib untuk template parameter_format=NAMED
        parameters.append(item)
    components: List[Dict[str, Any]] = []
    if media_id:
        components.append({"type": "header", "parameters": [
            {"type": "document", "document": {"id": media_id, "filename": filename}}]})
    components.append({"type": "body", "parameters": parameters})
    return await _post({
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": normalize_number(to), "type": "template",
        "template": {
            "name": c["template_doc"] if media_id else c["template"],
            "language": {"code": c["template_lang"]},
            "components": components,
        },
    })


async def send_document(to: str, media_id: str, filename: str = "laporan-penjualan.pdf",
                        caption: str = "") -> Dict[str, Any]:
    """Kirim PDF sebagai dokumen biasa + caption rekap.

    Hanya berhasil bila jendela 24 jam terbuka, tapi keunggulannya: caption boleh
    berisi rekap panjang (tidak dibatasi bentuk template).
    """
    doc: Dict[str, Any] = {"id": media_id, "filename": filename}
    if caption:
        doc["caption"] = caption[:1000]
    return await _post({
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": normalize_number(to), "type": "document", "document": doc,
    })


async def create_template(with_document: bool = False,
                          sample_pdf: Optional[bytes] = None) -> Dict[str, Any]:
    """Submit template rekap ke Meta (butuh META_WABA_ID + token berizin).

    Untuk versi berlampiran, contoh PDF diunggah dulu lewat Resumable Upload API
    agar Meta punya media contoh saat meninjau template.
    """
    c = _cfg()
    if not c["waba_id"]:
        raise WaError("META_WABA_ID belum diisi di backend/.env", retryable=False)
    handle = None
    if with_document:
        if not sample_pdf:
            raise WaError("Contoh PDF tidak tersedia untuk template berlampiran",
                          retryable=False)
        handle = await upload_sample_handle(sample_pdf)
    return await _request("POST", f"{c['waba_id']}/message_templates",
                          _template_create_payload(with_document=with_document,
                                                   header_handle=handle), retries=0)


async def list_templates() -> List[Dict[str, Any]]:
    """Status template di akun (APPROVED / PENDING / REJECTED)."""
    c = _cfg()
    if not c["waba_id"]:
        raise WaError("META_WABA_ID belum diisi di backend/.env", retryable=False)
    res = await _request("GET", f"{c['waba_id']}/message_templates",
                         params={"fields": "name,language,status,category,quality_score",
                                 "limit": 50}, retries=1)
    return res.get("data") or []


async def phone_status() -> Dict[str, Any]:
    """Cek nomor bisnis (verified_name, quality_rating, status CONNECTED)."""
    c = _cfg()
    if not c["phone_id"]:
        raise WaError("META_PHONE_NUMBER_ID belum diisi di backend/.env", retryable=False)
    return await _request("GET", c["phone_id"],
                          params={"fields": "verified_name,display_phone_number,"
                                            "quality_rating,code_verification_status"},
                          retries=1)


def template_values(snap: Dict[str, Any]) -> Dict[str, str]:
    """4 nilai ringkas untuk template: tanggal, omzet, laba bersih, transaksi."""
    return {
        "tanggal": tanggal_panjang(snap.get("date", "")),
        "omzet": rp(snap.get("omzet")),
        "laba_bersih": rp(snap.get("net_profit")),
        "jumlah_transaksi": num(snap.get("txn_count")),
    }


async def send_closing(snap: Dict[str, Any], store: Dict[str, Any], recipients: List[Dict[str, str]],
                       notes: str = "", pdf: Optional[bytes] = None,
                       pdf_filename: str = "laporan-penjualan.pdf",
                       pdf_url: str = "") -> Dict[str, Any]:
    """Kirim rekap + PDF Laporan Penjualan ke semua penerima.

    Selalu mengembalikan hasil per penerima + tautan 1-tap sebagai cadangan,
    dan TIDAK PERNAH melempar exception supaya proses tutup buku tetap sukses.

    Urutan usaha bila kredensial ada:
      1. Template BERLAMPIRAN PDF (header DOCUMENT) — satu-satunya cara sah
         mengirim file di luar jendela 24 jam. PDF diunggah SEKALI lalu media ID
         dipakai ulang untuk semua penerima.
      2. Template ringkas tanpa lampiran (bila template berlampiran belum disetujui).
      3. Dokumen biasa + caption rekap (berhasil bila owner baru membalas chat).
      4. Teks biasa.
      5. Tautan wa.me 1-tap berisi rekap + URL PDF — rekap tidak pernah hilang.
    """
    text = build_closing_text(snap, store, notes, pdf_url=pdf_url)
    values = template_values(snap)
    results = []
    configured = is_configured()

    # PDF diunggah sekali saja (media ID boleh dipakai untuk banyak penerima).
    media_id, media_error = None, None
    if configured and pdf:
        try:
            media_id = await upload_media_pdf(pdf, pdf_filename)
        except WaError as e:
            media_error = e.as_dict()
            logger.warning("Unggah PDF ke WhatsApp gagal: %s", str(e)[:200])
        except Exception as e:  # pragma: no cover
            media_error = {"message": str(e)[:300]}

    for rec in recipients:
        number = normalize_number(rec.get("number"))
        if not number:
            continue
        item = {"name": rec.get("name") or number, "number": number,
                "link": wa_me_link(number, text), "sent": False, "error": None,
                "via": None, "status": "manual", "pdf_attached": False}
        if not configured:
            results.append(item)
            continue

        attempts: List[tuple] = []
        if media_id:
            attempts.append(("template_pdf", lambda n=number: send_template(n, values, media_id, pdf_filename)))
        attempts.append(("template", lambda n=number: send_template(n, values)))
        if media_id:
            attempts.append(("document", lambda n=number: send_document(n, media_id, pdf_filename, text)))
        attempts.append(("text", lambda n=number: send_text(n, text)))

        last_err: Optional[WaError] = None
        for via, call in attempts:
            try:
                res = await call()
            except WaError as e:
                last_err = e
                # Error permanen yang BUKAN soal template/media -> berhenti,
                # mencoba jalur lain hanya akan menambah error yang sama.
                if e.code in (131026, 190, 0):
                    break
                continue
            except Exception as e:
                last_err = WaError(str(e)[:300])
                continue
            item["sent"] = True
            item["via"] = via
            item["status"] = "accepted"
            item["pdf_attached"] = via in ("template_pdf", "document")
            item["message_id"] = (res.get("messages") or [{}])[0].get("id")
            break

        if not item["sent"] and last_err is not None:
            item["error"] = str(last_err)[:300]
            item["hint"] = last_err.hint
            item["error_detail"] = last_err.as_dict()
        results.append(item)

    sent_count = sum(1 for r in results if r["sent"])
    return {
        "text": text,
        "template_values": values,
        "provider": provider_info(),
        "results": results,
        "sent_count": sent_count,
        "pdf_url": pdf_url,
        "pdf_size": len(pdf) if pdf else 0,
        "pdf_media_id": media_id,
        "pdf_error": media_error,
        # manual = owner perlu menekan tautan wa.me sekali
        "mode": "auto" if (configured and sent_count) else "manual",
    }
