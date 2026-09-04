"""Penjaga environment: menentukan apakah proses ini berjalan di PRODUCTION.

Dipakai untuk MEMBLOKIR TOTAL auto-seed data demo, produk contoh, dan akun demo
saat aplikasi berjalan di hosting sungguhan (Railway/Render/dll). Di production
data toko yang sudah dihapus/diubah owner TIDAK boleh muncul atau ter-reset lagi.

Aturan deteksi (cukup SATU yang terpenuhi -> dianggap production):
  1. RAILWAY_ENVIRONMENT / RAILWAY_ENVIRONMENT_NAME / RAILWAY_PROJECT_ID /
     RAILWAY_SERVICE_ID ada  -> Railway selalu menyuntikkan variabel ini otomatis.
  2. RENDER ada              -> Render menyuntikkan RENDER=true otomatis.
  3. APP_ENV / ENVIRONMENT / NODE_ENV / PYTHON_ENV bernilai
     "production" / "prod" / "live".
  4. DISABLE_SEED bernilai true/1/yes -> kunci manual (bisa dipakai di hosting mana pun).

Di Emergent/preview/lokal tidak ada satu pun variabel di atas, sehingga seed
tetap berjalan seperti biasa untuk memudahkan pengembangan.
"""
import logging
import os

logger = logging.getLogger("berkah")

_TRUE = {"1", "true", "yes", "on"}
_PROD_VALUES = {"production", "prod", "live"}

# Variabel yang disuntikkan otomatis oleh platform hosting (nilai apa pun = production).
_PLATFORM_MARKERS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
    "RENDER",
)

# Variabel konvensional yang nilainya menyatakan mode aplikasi.
_ENV_NAME_VARS = ("APP_ENV", "ENVIRONMENT", "NODE_ENV", "PYTHON_ENV")


def _val(name: str) -> str:
    return (os.environ.get(name) or "").strip().lower()


def production_reason() -> str | None:
    """Kembalikan alasan (nama variabel) mengapa dianggap production, atau None."""
    if _val("DISABLE_SEED") in _TRUE:
        return "DISABLE_SEED=true"
    for name in _PLATFORM_MARKERS:
        if os.environ.get(name):
            return f"{name}={os.environ.get(name)}"
    for name in _ENV_NAME_VARS:
        if _val(name) in _PROD_VALUES:
            return f"{name}={os.environ.get(name)}"
    return None


def is_production() -> bool:
    return production_reason() is not None


def seed_allowed() -> bool:
    """True HANYA di lokal/preview. Di production selalu False, tanpa pengecualian."""
    return not is_production()


def log_environment() -> None:
    reason = production_reason()
    if reason:
        logger.warning("MODE PRODUCTION terdeteksi (%s) -> auto-seed data demo, produk contoh, "
                       "dan akun demo DIBLOKIR. Password owner TIDAK di-reset.", reason)
    else:
        logger.info("Mode lokal/preview -> auto-seed data demo aktif (bukan production).")
