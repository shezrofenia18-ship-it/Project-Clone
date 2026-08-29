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

## Implemented (2026-08 — FASE 1: Mode Offline POS)
- Antrean penjualan offline tahan tutup-aplikasi (localStorage `bam_offline_queue`), auto-sync tiap 6s + saat event `online`.
- Tanggal/jam asli transaksi offline dipertahankan: frontend kirim `date` (tanggal lokal) + `offline_at`; backend simpan `created_at = offline_at`, `offline = true`, `synced_at`. Activity khusus "Penjualan Offline Tersinkron".
- Transaksi yang DITOLAK server tidak lagi dibuang diam-diam: ditandai `failed` + alasan, bisa Coba Lagi / Hapus.
- UI baru: badge topbar "N antre / N ditolak" (klik → dialog `PendingSales` dengan tombol "Sinkron Sekarang"), banner offline di POS.
- 2 BUG BESAR diperbaiki: (a) service worker tidak pernah cache app-shell → reload offline blank; fix mekanisme WARM_CACHE (index.js → SW postMessage) + navHandler fallback bertingkat, CACHE bam-v3, cacheFirst → stale-while-revalidate. (b) AuthContext menghapus token pada network error → kasir dipaksa logout saat offline; fix cache profil `bam_user`, sesi hanya dihapus bila server menolak (401).
- Teruji: backend 40/40 PASS (termasuk idempotency txn_id: stok/income/piutang tidak dobel). Frontend PASS: reload offline tetap jalan, sesi bertahan, antrean bertahan lintas reload, auto-sync, status "ditolak" tampil.

## Implemented (2026-08 — Export PDF Laporan)
- `backend/pdf_reports.py` (reportlab) + endpoint `/api/reports/{profit-loss,sales,stock}/pdf`, dipakai di `frontend/src/pages/Reports.js` & `Settings.js`.

## Environment restore (2026-08-29)
- Repo `shezrofenia18-ship-it/Project1` sudah tersambung; local `main` == `origin/main` (0 ahead/0 behind, HEAD 5492a78).
- Dependencies diinstall ulang (pip requirements.txt + yarn install ~945 paket). backend & frontend RUNNING, login owner → dashboard OK.
- `memory/test_credentials.md` dibuat ulang (sempat hilang).

## Implemented (2026-08-29 — FASE 2: Realtime WebSocket + Tutup Buku + HPP per ekor)
- **Realtime WebSocket** (`backend/realtime.py`, `frontend/src/context/RealtimeContext.js`): endpoint `WS /api/ws?token=<jwt>`; server hanya kirim sinyal `{"type":"invalidate","topics":[...]}` (otorisasi tetap di REST). Emit dipasang di helper bersama `add_activity` → dashboard/activities, `add_notification` → notifications, `apply_stock` → stock/products, plus sale/cancel/expense/target/produk/tutup-buku. `emit()` menelan exception → penjualan tidak pernah gagal karena socket.
  - Frontend: reconnect backoff max 30s, stop bila close 1008, reconnect saat event `online`, event digabung (debounce 250ms). `usePoll(path, interval, topics)` → interval 60s saat live, kembali cepat saat socket mati (FALLBACK POLLING, app tidak pernah mati). `useRealtimeReload(topics, reload)` untuk halaman useFetch. Badge **LIVE** di topbar. Dipakai di Dashboard, notifikasi, POS, Stok, Produk, Tutup Buku.
- **Tutup Buku Harian** (`/tutup-buku`, owner+admin; POST owner saja): `_closing_snapshot(date)` → omzet, HPP, laba kotor/bersih, margin, kas per metode bayar, piutang baru, bayar piutang masuk, pengeluaran per kategori, pembelian, produk terjual, stok sisa + nilai, posisi piutang/hutang, target. Endpoint `GET /api/daily-closing/preview`, `POST /api/daily-closing` (upsert per tanggal, version++), `GET /api/daily-closing` (riwayat), `GET /api/daily-closing/{id|tanggal}`, `/pdf` (reportlab, 7 bagian A–G + tanda tangan). Index unique `daily_closings.date`.
- **HPP per ekor berbasis berat perkiraan** (permintaan user: toko jual per ekor, beli ditimbang): produk punya `cum_ekor_in`, `cum_weight_in`, `avg_weight_ekor` (auto = kumulatif kg ÷ ekor dari SEMUA ayam masuk), `avg_weight_override` (manual owner, 0 = auto), `avg_weight_used`, `avg_weight_source`. `hpp_ekor = hpp_kg × berat efektif`. Pembelian menambah akumulator, hapus/ubah pembelian menguranginya. Endpoint `POST /api/products/{id}/avg-weight`. UI: kolom Berat/ekor + HPP/ekor, badge `manual` & `isi berat`, field override + tombol "Pakai Otomatis".
  - Catatan: untuk 1 pembelian tunggal hasilnya identik formula lama (tanpa regresi); manfaatnya muncul saat berat kiriman berbeda-beda (dihaluskan).
- Teruji: testing agent backend **28/28 PASS** (HPP/ekor 5/5, tutup buku 10/10, websocket 5/5, regresi 8/8), 0 error log.

## Known gaps
- Ayam Kampung & Ayam Pejantan punya harga jual/ekor tapi belum pernah dibeli per ekor → `hpp_ekor` masih 0 (ditandai badge "isi berat" di Produk & Harga). Owner perlu mengisi berat perkiraan/ekor sekali agar laba per ekor akurat.
- Temuan bisnis: Ayam Broiler jual/ekor Rp 55.000 vs modal efektif/ekor Rp 54.540 → laba hanya Rp 460/ekor (0,8%). Sebelumnya terlihat 100% laba karena hpp_ekor = 0. Perlu ditinjau owner.
- Fix RBAC (2026-08-29): baris "Modal efektif/laba" di dialog POS kini hanya tampil untuk owner/admin (`canSeeCost` di `EntryDialog`), sebelumnya bocor ke kasir begitu hpp_ekor terisi.
- Dashboard products_perf belum agregasi volume unit pcs (nilai penjualan/hpp/laba tetap benar).

## Backlog / Remaining
- P1: Harga khusus pelanggan per produk otomatis di POS — FASE 3, disetujui user (field `special_prices` sudah ada di backend, belum ada UI & belum dipakai POS).
- P2: Multi-cabang (stores), integrasi timbangan digital, export Excel native.

## Test Credentials
Lihat `/app/memory/test_credentials.md`.
