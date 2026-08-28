# PRD — BERKAH AYAM MILI (Sistem POS & Manajemen Ayam Potong)

## Problem Statement
Aplikasi web/PWA manajemen bisnis ayam potong "Berkah Ayam Mili": penjualan (kg/ekor/kombinasi), pembelian, stok, pemotongan (rendemen/susut), produksi fillet, HPP aktual, laba, margin, pemasukan/pengeluaran, hutang/piutang, pelanggan, supplier, target, laporan, dashboard owner, monitoring real-time, multi-user RBAC, audit log. Bahasa Indonesia, format Rp & kg.

## Architecture
- Backend: FastAPI (`/app/backend`), modular (`db.py`, `auth.py`, `seed.py`, `server.py`). MongoDB via motor. JWT (Bearer) auth, RBAC (owner/admin/kasir/operator). All routes `/api`.
- Frontend: React 19 + CRACO, Tailwind, shadcn/ui, recharts, sonner. Token in localStorage `bam_token`. Role-based routing & views. PWA manifest.
- Realtime: polling (dashboard 8s, notifications 12s) + ONLINE/OFFLINE status.

## User Personas
- Kasir (Tablet): POS cepat, tombol besar. Tidak lihat HPP/laba/laporan.
- Operator: Pemotongan, produksi, stok, penerimaan.
- Admin: Master data, pembelian, laporan.
- Owner: Akses penuh + dashboard, target, keuangan, pengguna, pengaturan.

## Core Requirements (static)
Flow: Pembelian → Stok → Pemotongan → Karkas → Fillet → Stok → Penjualan → HPP → Laba → Margin → Pemasukan/Pengeluaran → Laporan. Semua angka dari database, kontrol stok negatif, audit trail, idempotency penjualan (txn_id).

## Implemented (2026-06)
- Auth JWT + RBAC, 4 role, seeding owner + demo staff.
- Master produk & harga (beli/HPP/jual kg&ekor), price history.
- POS: kg (keypad desimal), ekor (stepper), kombinasi, 6 metode bayar, piutang, idempotency, kontrol stok.
- Pembelian (modal efektif/kg, hutang, expense otomatis), Pemotongan (rendemen/susut), Produksi fillet (HPP fillet, byproduct).
- Stok + stock movements + penyesuaian (rusak/mati/susut).
- Pelanggan, Supplier (+ perbandingan harga), Hutang/Piutang + pembayaran.
- Pemasukan/Pengeluaran, Target harian, Dashboard owner (kartu, grafik 7 hari, performa produk, aktivitas, transaksi terbaru, stok kritis, harga terkini).
- Laporan (laba rugi, penjualan, stok) + export CSV + cetak. Audit log. Pengguna. Pengaturan (stok negatif, nama toko). Notifikasi.
- Demo data realistis & terhubung. Testing: backend 25/25 pass, frontend core flows pass.

## Implemented (2026-06 update)
- Pembelian by TOTAL nominal supplier → estimasi harga beli/kg (total÷berat), modal efektif/kg, modal efektif/ekor (hpp_ekor). Owner tak input harga/kg manual.
- Produk sampingan dapat dijual per pcs ATAU per kg (units ["kg","pcs"], price_pcs/hpp_pcs). POS EntryDialog toggle unit pcs.
- Tambah produk sampingan "Paha Ayam".
- Rename "Produksi Fillet" → "Produksi Potong" (nav + halaman).
- Fix: cancel_sale kini mengembalikan stok pcs (delta_pcs). POS.js hook priceFor distabilkan via useCallback.
- Testing agent iterasi 5: backend 27/27 pass, frontend 5/5 pass. pcs sale+cancel diverifikasi via API.

## Known minor gaps (dari review iter 5, belum dikerjakan)
- Dashboard products_perf belum agregasi volume unit pcs (penjualan/hpp/laba tetap benar; hanya counter volume kg/ekor).
- create_purchase: item ekor=0 & berat>0 → hpp_ekor 0 diam-diam (guard div-by-zero ada).

## Backlog / Remaining
- P1: PWA offline queue + sync (IndexedDB) — user setuju menyusul.
- P1: WebSocket realtime (saat ini polling).
- P2: Multi-cabang (stores), harga khusus per pelanggan di POS otomatis, integrasi timbangan digital, export PDF/Excel native, edit/hapus pembelian.

## Test Credentials
Lihat `/app/memory/test_credentials.md`.
