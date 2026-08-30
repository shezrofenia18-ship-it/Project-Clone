"""
Lapisan penyimpanan berkas yang PORTABEL (foto produk & bukti pengeluaran).

Tujuan modul ini: aplikasi bisa dipindah hosting TANPA mengubah kode.
Cukup isi environment variable, backend akan memilih penyimpanan sendiri.

Tiga penyedia didukung:

1. "s3"        -> S3-compatible: Cloudflare R2, AWS S3, MinIO, Backblaze B2, dsb.
                  Dipakai bila S3_BUCKET + kunci akses tersedia. INI PILIHAN
                  UNTUK PRODUKSI DI LUAR EMERGENT.
2. "emergent"  -> Object storage bawaan platform Emergent. Hanya hidup selama
                  aplikasi berjalan DI DALAM Emergent.
3. "local"     -> Folder di disk server. Berguna untuk pengembangan di laptop.
                  PERINGATAN: di hosting seperti Railway/Render/Vercel, disk
                  bersifat sementara — berkas HILANG setiap kali redeploy.

Pemilihan otomatis (STORAGE_BACKEND="auto", bawaan):
    ada kredensial S3 ........ -> s3
    ada EMERGENT_LLM_KEY ..... -> emergent
    tidak ada keduanya ....... -> local

Bisa juga dipaksa: STORAGE_BACKEND=s3 | emergent | local

Antarmuka yang dipakai server.py (sengaja dijaga tetap sama seperti versi lama
supaya tidak ada perubahan perilaku):
    init_storage(force=False) -> None/str
    put_object(path, data, content_type) -> dict {"path": ..., "size": ...}
    get_object(path) -> (bytes, content_type)
    active_backend() -> str
    describe() -> str
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Modul ini membaca environment variable SAAT DIIMPOR untuk menentukan penyedia
# penyimpanan. Memuat .env di sini membuatnya aman diimpor dari mana saja
# (server.py, skrip perawatan, atau pengujian) tanpa bergantung pada urutan
# impor. load_dotenv() tidak menimpa variabel yang sudah diset hosting.
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("berkah")


def _env(name: str, default: str = "") -> str:
    """Ambil env var lalu rapikan. Hosting sering menyisakan spasi/kutip."""
    return (os.environ.get(name) or default).strip().strip('"').strip("'")


# --------------------------------------------------------------------------
# Konfigurasi
# --------------------------------------------------------------------------
STORAGE_BACKEND = (_env("STORAGE_BACKEND", "auto") or "auto").lower()

# --- S3 / Cloudflare R2 ---
S3_BUCKET = _env("S3_BUCKET")
S3_ACCESS_KEY_ID = _env("S3_ACCESS_KEY_ID") or _env("AWS_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = _env("S3_SECRET_ACCESS_KEY") or _env("AWS_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = _env("S3_ENDPOINT_URL")
# Cloudflare R2 mewajibkan region "auto".
S3_REGION = _env("S3_REGION") or ("auto" if "r2.cloudflarestorage.com" in S3_ENDPOINT_URL else "us-east-1")

# --- Emergent ---
EMERGENT_KEY = _env("EMERGENT_LLM_KEY")
_STORAGE_BASE = _env("INTEGRATION_PROXY_URL") or "https://integrations.emergentagent.com"
EMERGENT_STORAGE_URL = _STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"

# --- Local ---
LOCAL_DIR = Path(_env("LOCAL_STORAGE_DIR") or (Path(__file__).parent / "uploads"))


def _has_s3_config() -> bool:
    return bool(S3_BUCKET and S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY)


def _resolve_backend() -> str:
    if STORAGE_BACKEND in ("s3", "emergent", "local"):
        return STORAGE_BACKEND
    if _has_s3_config():
        return "s3"
    if EMERGENT_KEY:
        return "emergent"
    return "local"


BACKEND = _resolve_backend()


def active_backend() -> str:
    return BACKEND


def describe() -> str:
    """Ringkasan aman untuk log — TIDAK pernah memuat kunci rahasia."""
    if BACKEND == "s3":
        where = S3_ENDPOINT_URL or "AWS S3"
        return f"s3 (bucket={S3_BUCKET}, endpoint={where}, region={S3_REGION})"
    if BACKEND == "emergent":
        return "emergent (hanya berfungsi di dalam platform Emergent)"
    return f"local (folder={LOCAL_DIR}) - PERINGATAN: berkas hilang saat redeploy"


# --------------------------------------------------------------------------
# Penyedia 1: S3-compatible (Cloudflare R2 / AWS S3 / MinIO)
# --------------------------------------------------------------------------
_s3_client = None


def _s3():
    """Klien boto3 dibuat sekali saja, dan diimpor secara lazy supaya
    penyedia lain tidak wajib punya boto3 terpasang."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    import boto3
    from botocore.config import Config

    kwargs = {
        "aws_access_key_id": S3_ACCESS_KEY_ID,
        "aws_secret_access_key": S3_SECRET_ACCESS_KEY,
        "region_name": S3_REGION,
        # signature v4 wajib untuk R2; path-style menghindari masalah DNS bucket.
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"},
                         retries={"max_attempts": 3, "mode": "standard"}),
    }
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
    _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def _s3_put(path: str, data: bytes, content_type: str) -> dict:
    _s3().put_object(Bucket=S3_BUCKET, Key=path, Body=data, ContentType=content_type)
    return {"path": path, "size": len(data)}


def _s3_get(path: str):
    obj = _s3().get_object(Bucket=S3_BUCKET, Key=path)
    return obj["Body"].read(), obj.get("ContentType") or "application/octet-stream"


# --------------------------------------------------------------------------
# Penyedia 2: Emergent object storage
# --------------------------------------------------------------------------
_emergent_key = None


def _emergent_init(force: bool = False) -> str:
    global _emergent_key
    if _emergent_key and not force:
        return _emergent_key
    resp = requests.post(f"{EMERGENT_STORAGE_URL}/init",
                         json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _emergent_key = resp.json()["storage_key"]
    return _emergent_key


def _emergent_put(path: str, data: bytes, content_type: str) -> dict:
    key = _emergent_init()
    url = f"{EMERGENT_STORAGE_URL}/objects/{path}"
    headers = {"X-Storage-Key": key, "Content-Type": content_type}
    resp = requests.put(url, headers=headers, data=data, timeout=120)
    if resp.status_code == 404:
        # Kunci storage kedaluwarsa: ambil ulang lalu coba sekali lagi.
        headers["X-Storage-Key"] = _emergent_init(force=True)
        resp = requests.put(url, headers=headers, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _emergent_get(path: str):
    key = _emergent_init()
    resp = requests.get(f"{EMERGENT_STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# --------------------------------------------------------------------------
# Penyedia 3: disk lokal
# --------------------------------------------------------------------------
def _local_path(path: str) -> Path:
    """Cegah path traversal (mis. "../../etc/passwd") sebelum menyentuh disk."""
    target = (LOCAL_DIR / path).resolve()
    root = LOCAL_DIR.resolve()
    if root != target and root not in target.parents:
        raise ValueError("Path berkas tidak sah")
    return target


def _local_put(path: str, data: bytes, content_type: str) -> dict:
    target = _local_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    # Content-type disimpan berdampingan agar tetap benar saat dibaca kembali.
    target.with_suffix(target.suffix + ".type").write_text(content_type)
    return {"path": path, "size": len(data)}


def _local_get(path: str):
    target = _local_path(path)
    if not target.exists():
        raise FileNotFoundError(path)
    meta = target.with_suffix(target.suffix + ".type")
    ct = meta.read_text().strip() if meta.exists() else "application/octet-stream"
    return target.read_bytes(), ct


# --------------------------------------------------------------------------
# Antarmuka publik
# --------------------------------------------------------------------------
def init_storage(force: bool = False):
    """Dipanggil sekali saat startup. TIDAK boleh menggagalkan startup —
    kalau penyimpanan bermasalah, aplikasi kasir harus tetap bisa jualan."""
    if BACKEND == "s3":
        # head_bucket memverifikasi kredensial & keberadaan bucket lebih awal,
        # supaya salah ketik ketahuan saat start, bukan saat kasir upload.
        _s3().head_bucket(Bucket=S3_BUCKET)
        return "s3"
    if BACKEND == "emergent":
        return _emergent_init(force=force)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    return str(LOCAL_DIR)


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if BACKEND == "s3":
        return _s3_put(path, data, content_type)
    if BACKEND == "emergent":
        return _emergent_put(path, data, content_type)
    return _local_put(path, data, content_type)


def get_object(path: str):
    if BACKEND == "s3":
        return _s3_get(path)
    if BACKEND == "emergent":
        return _emergent_get(path)
    return _local_get(path)
