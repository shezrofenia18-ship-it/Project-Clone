"""
Penyimpanan berkas (foto produk & bukti pengeluaran) di Cloudflare R2 (S3-compatible).

TIDAK ADA lagi penyimpanan ke folder lokal server. Disk di Railway/Render/Vercel
bersifat sementara sehingga foto hilang setiap redeploy — karena itu satu-satunya
penyedia yang didukung adalah object storage R2 (lewat boto3).

Environment variable yang dibaca (JANGAN di-hardcode):
    R2_ENDPOINT_URL        https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID       dari "Manage R2 API Tokens" (Object Read & Write)
    R2_SECRET_ACCESS_KEY   dari "Manage R2 API Tokens"
    R2_BUCKET_NAME         nama bucket, mis. berkah-ayam-mili
    R2_PUBLIC_URL_BASE     domain publik bucket (r2.dev atau custom domain),
                           mis. https://pub-xxxx.r2.dev  atau  https://foto.tokoanda.com

Alur upload: berkas dikirim ke R2 dengan Content-Type asli (image/jpeg, dst.)
supaya browser langsung merendernya sebagai gambar, lalu URL publik dibentuk dari
R2_PUBLIC_URL_BASE + "/" + nama objek dan disimpan sebagai teks di MongoDB
(field `image_url` produk / `proof_url` pengeluaran).

Antarmuka yang dipakai server.py:
    is_configured() -> bool
    missing_config() -> list[str]        # nama env yang belum terisi
    init_storage() -> str                # verifikasi bucket saat startup
    upload_object(key, data, content_type) -> dict {"key", "url", "size"}
    get_object(key) -> (bytes, content_type)   # cadangan bila bucket privat
    public_url(key) -> str
    active_backend() -> str
    describe() -> str                    # ringkasan aman untuk log (tanpa rahasia)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Muat .env agar modul aman diimpor dari mana pun (server, skrip, pengujian).
# load_dotenv() TIDAK menimpa variabel yang sudah diset oleh hosting.
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("berkah")

REQUIRED_ENV = (
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_PUBLIC_URL_BASE",
)


def _env(name: str, default: str = "") -> str:
    """Ambil env var lalu rapikan. Hosting sering menyisakan spasi/kutip."""
    return (os.environ.get(name) or default).strip().strip('"').strip("'")


def _cfg() -> dict:
    """Konfigurasi dibaca SAAT DIPANGGIL (bukan saat impor) supaya perubahan
    env + restart langsung berlaku dan mudah diuji."""
    return {
        "endpoint": _env("R2_ENDPOINT_URL").rstrip("/"),
        "access_key": _env("R2_ACCESS_KEY_ID"),
        "secret_key": _env("R2_SECRET_ACCESS_KEY"),
        "bucket": _env("R2_BUCKET_NAME"),
        "public_base": _env("R2_PUBLIC_URL_BASE").rstrip("/"),
    }


def missing_config() -> list:
    return [name for name in REQUIRED_ENV if not _env(name)]


def is_configured() -> bool:
    return not missing_config()


def active_backend() -> str:
    return "r2" if is_configured() else "unconfigured"


def describe() -> str:
    """Ringkasan aman untuk log — TIDAK pernah memuat kunci rahasia."""
    c = _cfg()
    if not is_configured():
        return ("Cloudflare R2 BELUM dikonfigurasi (env kosong: "
                + ", ".join(missing_config()) + ") - upload foto akan ditolak")
    return f"Cloudflare R2 (bucket={c['bucket']}, endpoint={c['endpoint']}, public={c['public_base']})"


# --------------------------------------------------------------------------
# Klien boto3
# --------------------------------------------------------------------------
_client = None
_client_sig = None


def _s3():
    """Klien boto3 dibuat sekali per konfigurasi (dibuat ulang bila env berubah)."""
    global _client, _client_sig
    c = _cfg()
    if not is_configured():
        raise RuntimeError("Cloudflare R2 belum dikonfigurasi: " + ", ".join(missing_config()))
    sig = (c["endpoint"], c["access_key"], c["secret_key"], c["bucket"])
    if _client is not None and _client_sig == sig:
        return _client
    import boto3
    from botocore.config import Config

    _client = boto3.client(
        "s3",
        endpoint_url=c["endpoint"],
        aws_access_key_id=c["access_key"],
        aws_secret_access_key=c["secret_key"],
        # R2 mewajibkan region "auto" dan signature v4.
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"max_attempts": 3, "mode": "standard"}),
    )
    _client_sig = sig
    return _client


# --------------------------------------------------------------------------
# Antarmuka publik
# --------------------------------------------------------------------------
def public_url(key: str) -> str:
    """URL publik utuh = R2_PUBLIC_URL_BASE + '/' + nama objek."""
    return f"{_cfg()['public_base']}/{key.lstrip('/')}"


def init_storage() -> str:
    """Dipanggil sekali saat startup. Bila R2 belum dikonfigurasi, hanya
    memperingatkan (aplikasi kasir harus tetap bisa jualan). Bila sudah,
    head_bucket memverifikasi kredensial & bucket lebih awal supaya salah
    ketik ketahuan saat start, bukan saat owner mengunggah foto."""
    if not is_configured():
        logger.warning(describe())
        return "unconfigured"
    _s3().head_bucket(Bucket=_cfg()["bucket"])
    return "r2"


def upload_object(key: str, data: bytes, content_type: str) -> dict:
    """Unggah berkas ke R2 dengan Content-Type yang sesuai, kembalikan URL publiknya."""
    _s3().put_object(
        Bucket=_cfg()["bucket"],
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
        # Boleh di-cache lama oleh browser/CDN karena nama objek unik per upload.
        CacheControl="public, max-age=31536000, immutable",
    )
    return {"key": key, "url": public_url(key), "size": len(data)}


def get_object(key: str):
    """Ambil isi objek dari R2 (dipakai endpoint cadangan /api/files/{id})."""
    obj = _s3().get_object(Bucket=_cfg()["bucket"], Key=key)
    return obj["Body"].read(), obj.get("ContentType") or "application/octet-stream"


# Kompatibilitas nama lama (put_object) agar skrip/pengujian lama tidak pecah.
def put_object(path: str, data: bytes, content_type: str) -> dict:
    r = upload_object(path, data, content_type)
    return {"path": r["key"], "url": r["url"], "size": r["size"]}
