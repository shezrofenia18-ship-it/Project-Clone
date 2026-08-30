"""Perbaikan data warisan: dokumen bertanggal MASA DEPAN.

Latar masalah nyata yang dilaporkan owner: setelah menjual 1 ekor Ayam Broiler,
stok berkurang tetapi transaksinya "tidak muncul" di Riwayat Transaksi.
Penyebabnya BUKAN penjualan gagal tersimpan, melainkan data demo yang diberi jam
acak 07:00-20:00 tanpa melihat jam sekarang. Akibatnya ada dokumen dengan
`created_at` di MASA DEPAN, dan karena Riwayat Transaksi urut dari terbaru,
transaksi asli kasir tertimbun di bawah baris-baris demo tersebut.

Modul ini menggeser seluruh dokumen bertanggal masa depan ke masa lalu:
- SATU pergeseran (shift) global dipakai untuk semua koleksi, sehingga urutan
  relatif antar dokumen dan keterkaitan (penjualan <-> uang masuk <-> aktivitas
  yang waktunya berdempet) tetap konsisten.
- Nilai uang/qty TIDAK PERNAH diubah, hanya `created_at`.
- Tanggal kalender (`date`) dijaga tidak berpindah hari, agar laporan harian dan
  tutup buku tetap cocok.
- Idempoten: setelah dijalankan tidak ada lagi dokumen masa depan, jadi
  pemanggilan berikutnya tidak melakukan apa pun.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger("berkah")

JKT = timezone(timedelta(hours=7))

# Koleksi yang punya `created_at` dan ikut menentukan urutan tampilan/laporan.
TIME_COLLECTIONS = (
    "sales", "incomes", "expenses", "activities", "stock_movements", "notifications",
    "receivables", "debts", "purchases", "slaughters", "productions", "adjustments",
    "returns", "audit_logs", "wa_logs",
)


def _parse(value: Any):
    """Baca ISO datetime; kembalikan None bila bukan waktu yang bisa dipakai."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=JKT)


async def _collect_future(db, now: datetime) -> Dict[str, List[dict]]:
    """Kumpulkan dokumen `created_at` > sekarang per koleksi."""
    now_iso = now.isoformat()
    found: Dict[str, List[dict]] = {}
    existing = set(await db.list_collection_names())
    for name in TIME_COLLECTIONS:
        if name not in existing:
            continue
        rows = await db[name].find(
            {"created_at": {"$gt": now_iso}},
            {"id": 1, "created_at": 1, "date": 1},
        ).to_list(20000)
        rows = [r for r in rows if _parse(r.get("created_at")) and _parse(r["created_at"]) > now]
        if rows:
            found[name] = rows
    return found


async def repair_future_timestamps(db) -> int:
    """Geser dokumen bertanggal masa depan ke masa lalu. Balikan: jumlah dokumen."""
    now = datetime.now(JKT)
    future = await _collect_future(db, now)
    if not future:
        return 0

    # Titik acuan: dokumen termuda di masa depan diletakkan 5 menit sebelum sekarang,
    # lalu SEMUA dokumen digeser dengan selisih yang sama.
    latest = max(_parse(r["created_at"]) for rows in future.values() for r in rows)
    shift = latest - (now - timedelta(minutes=5))
    if shift <= timedelta(0):
        return 0

    total = 0
    for name, rows in future.items():
        for r in rows:
            original = _parse(r["created_at"])
            moved = original - shift
            # Jangan sampai berpindah hari: laporan harian & tutup buku memakai
            # field `date`, jadi waktu ditahan minimal di 00:01 hari yang sama.
            day_floor = original.replace(hour=0, minute=1, second=0, microsecond=0)
            if moved < day_floor:
                moved = day_floor
            await db[name].update_one({"_id": r["_id"]},
                                      {"$set": {"created_at": moved.isoformat()}})
            total += 1
        logger.info("Perbaikan waktu: %s dokumen '%s' digeser ke masa lalu", len(rows), name)

    logger.warning("Perbaikan waktu selesai: %s dokumen bertanggal masa depan digeser "
                   "%.1f jam ke belakang (transaksi baru kini selalu tampil paling atas)",
                   total, shift.total_seconds() / 3600)
    return total
