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

## Implemented (2026-08-30 sore — 3 permintaan lanjutan)
- **POS: opsi ukuran kartu** (`POS.js`): picker `pos-card-size` (Kecil/Sedang/Besar) di kanan baris kategori; kolom Kecil 3/5/6/8 · Sedang 3/4/5/6 · Besar 2/3/4/5 (HP/tablet/lg/2xl), padding + ukuran teks & foto ikut menyesuaikan; pilihan disimpan per perangkat di localStorage `bam_pos_card_size`. Teruji di HP 390 (3/3/2), tablet 820 (5/4/3), desktop 1920 (8/6/5), bertahan setelah reload & pindah halaman.
- **Pembelian Baru** (`Purchases.js`): tiap item jadi kartu ber-border dengan label di ATAS setiap kotak — Produk · Jumlah (ekor) · Berat Total (kg) · Total Harga (Rp) — plus satuan di dalam kotak lewat komponen `UnitField`; responsif (grid-cols-2 di HP → sm:grid-cols-12). Kolom **Transport & Biaya Lain DIHAPUS** (payload tidak lagi mengirim `transport_cost`/`other_cost`; backend default 0) → Total Modal = total harga ayam. "Dibayar" → "Dibayar Sekarang (Rp)" + hint hutang supplier. Teruji backend 9/9 (total_modal 500rb, modal efektif 25rb/kg & 50rb/ekor, stok +20kg/+10ekor, hapus → semua kembali).
- **Halaman Stok tanpa rupiah** (`Stock.js`): subtitle "Nilai stok: Rp…" → "Total stok: … kg · … ekor"; baris "Nilai: Rp…" per kartu dihapus. Nilai rupiah stok TETAP di Laporan > Stok (owner/admin) + PDF.
- CATATAN GAP (belum dikerjakan): `DELETE /api/purchases/{id}` mengembalikan stok/expense/hutang, TAPI tidak mengembalikan `hpp_kg`/`hpp_ekor` produk ke nilai sebelum pembelian (HPP tetap memakai harga pembelian terakhir yang dihapus). Perlu diperbaiki bila owner sering menghapus pembelian salah input.

## Implemented (2026-08-30 — 5 permintaan owner)
1. **POS Kasir dipadatkan & responsif** (`frontend/src/pages/POS.js`): grid produk 3 (HP) / 4 (tablet) / 5 (desktop) / 6 (≥1536px) kolom, foto `aspect-square`, teks 13px/10px; chip kategori h-8; banner offline tipis; sidebar keranjang 380→320px; bar bawah HP lebih tipis (tombol "Keranjang"); sheet keranjang 80vh; EntryDialog & dialog Pembayaran compact (max-w-sm, input/keypad h-10) → keypad + tombol "Tambah ke Keranjang" muat di HP tanpa scroll.
2. **Modal efektif & laba/satuan DIHAPUS TOTAL dari POS** untuk semua role (helper `modalOf` dibuang; `data-testid="entry-modal"` tidak ada lagi). Peringatan "berat perkiraan" pindah ke baris "Stok berkurang" (tanpa nominal). Owner tetap melihat modal/laba di Produk & Harga, Laporan, Dashboard.
3. **Laporan Laba Rugi BULANAN + PDF arsip**: `GET /api/reports/monthly?month=YYYY-MM` (owner/admin, default bulan ini WIB; rumus finance.summarize sama dgn dashboard/tutup buku) → ringkasan, `daily[]` per hari, `products[]` top 30, `prev{}` & `growth{}`; `GET /api/reports/monthly/pdf` → PDF landscape berkop toko (`pdf_reports.monthly_pl_pdf`: ringkasan, perbandingan bulan lalu, rincian harian + TOTAL, beban per kategori, arus kas, performa produk, tanda tangan). Frontend: tab **"Bulanan (Arsip)"** di `Reports.js` (pemilih bulan, 4 kartu, tabel harian, Unduh PDF, Export CSV; filter tanggal harian disembunyikan saat tab ini aktif → `Tabs` jadi controlled).
4. **Pengeluaran kasir hanya miliknya**: `create_expense` menyimpan `created_by_id`/`created_by_role`; `list_expenses` untuk kasir difilter `created_by_id == user.id` (fallback nama untuk dokumen lama). Owner/admin tetap melihat SEMUA (termasuk input kasir) → laporan/dashboard/tutup buku owner tidak berubah.
5. **Riwayat transaksi kasir dibatasi 7 hari** di SERVER (`KASIR_HISTORY_DAYS=7`, `kasir_history_min_date()`): tanpa `date` → `date >= hari ini-6`; `?date` lebih lama → `[]`. Endpoint bantu `GET /api/sales/access`. UI kasir: kalender min/max, tombol "7 Hari Terakhir", catatan penjelas. Owner/admin tidak dibatasi.

Teruji: backend 22/22 PASS (termasuk regresi owner & RBAC 403 kasir untuk laporan bulanan), frontend 40/41 PASS di viewport HP 390 / tablet 820 & 1024 / desktop 1920 (checkout HP sampai struk, lalu dibatalkan owner). Data uji dibersihkan.

## Environment restore (2026-08-30)
- Repo `shezrofenia18-ship-it/Project1` tersambung. Branch aktif `conflict_290826_1811` (HEAD e198d99) == `origin/conflict_290826_1811` — ini commit TERBARU (30 Ags). `origin/main` tertinggal 18 commit; hanya beda 1 commit config `.emergent/emergent.yml`.
- Dependencies diinstall ulang: pip requirements.txt (reportlab jadi 5.0.1, export PDF diverifikasi tetap jalan) + yarn install. backend & frontend RUNNING; login owner → Dashboard OK.
- `memory/test_credentials.md` dibuat ulang (file ini tidak ikut ter-commit).

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

## Environment restore (2026-08-29, sesi lanjutan)
- Repo `shezrofenia18-ship-it/Project1` tersambung; local `main` == `origin/main` (0 ahead / 0 behind, HEAD `493a07a`). Semua commit terakhir (realtime WS, tutup buku, HPP/ekor, offline POS, PDF) ada di workspace.
- Dependencies diinstall ulang: pip requirements.txt (reportlab 5.0.1, `pdf_reports` import OK) + yarn install (945 paket).
- backend & frontend RUNNING; live preview terverifikasi: login owner → Dashboard Owner tampil data nyata (omzet Rp 3.743.030, 14 transaksi, badge ONLINE + LIVE aktif).
- `memory/test_credentials.md` dibuat ulang (owner/admin/kasir; password kasir Budi tidak diketahui).
- CATATAN KEAMANAN: user menempel GitHub PAT di chat → harus di-revoke.

## Implemented (2026-08-29 — FASE 4a: Berat Perkiraan Bawaan per Ekor + Rekap WhatsApp diperluas)
- **Berat perkiraan bawaan (fallback)** — permintaan user: "pandu owner mengisi berat perkiraan Ayam Kampung & Pejantan, JIKA TIDAK DIISI TETAP DENGAN PERKIRAAN".
  Prioritas berat efektif/ekor: `manual (override owner)` > `auto (rata-rata pembelian)` > `perkiraan (DEFAULT_AVG_WEIGHT)`.
  Default per nama produk: broiler 1.8 · kampung 1.2 · pejantan 1.1 · petelur 1.6 · ayam lain 1.5 (fallback 1.5).
  Hanya untuk produk per-ekor (`sells_per_ekor`), jadi produk potongan/fillet tetap `hpp_ekor = 0` (benar).
  Field baru: `avg_weight_default`, `avg_weight_is_estimate`; `refresh_all_avg_weights()` idempoten di startup.
  Endpoint baru `GET /api/products/weight-guidance` (owner+admin) → need_confirm, thin_margin_count, items dgn profit_ekor/margin_ekor/thin_margin.
  UI Produk & Harga: panel **"Panduan Berat per Ekor"** (bisa disembunyikan, tersimpan di localStorage) berisi input cepat per produk + tombol "Pakai X kg", plus peringatan **laba/ekor tipis (<5%)**; badge kuning **perkiraan** di tabel & dialog; POS menandai "berat perkiraan" pada baris modal (owner/admin saja).
  Efeknya: Ayam Kampung `hpp_ekor` 62.400 (52.000 × 1,2), Ayam Pejantan 36.300 (33.000 × 1,1) — sebelumnya 0 sehingga laba/ekor tampak 100%.
- **Rekap WhatsApp** (sudah ada dari sesi sebelumnya, kini diuji + diperluas): collection `wa_logs`, `GET /api/whatsapp/log`, `POST /api/whatsapp/test` (owner), trigger tercatat `manual`/`otomatis`/`uji coba`; UI Pengaturan dapat tombol **Kirim Uji Coba** + **Riwayat pengiriman terakhir**.
  Mode aktif = **1-tap manual** (kredensial Meta belum diberikan user). Begitu `META_PHONE_NUMBER_ID` + `META_ACCESS_TOKEN` (+ `WA_TEMPLATE_NAME`) diisi di backend/.env, pengiriman otomatis jam 21:00 WIB langsung aktif tanpa ubah kode.
- Teruji: testing agent backend **14/14 PASS** (berat perkiraan 6/6, WhatsApp 7/7, regresi 11/11).
- Bersih-bersih data uji: 2 pembelian uji dihapus (stok & akumulator pulih), harga Ayam Kampung dikembalikan ke nilai demo (beli 45.000 · HPP 52.000 · jual 62.000).

## Code review hardening (2026-08-29)
- `pdf_reports.tgl/tgl_singkat`: tangkap `(TypeError, ValueError)` + validasi bulan → PDF tak bisa crash karena tanggal aneh.
- `server.serve_file`: `Response` dibangun di dalam `try` (tidak ada variabel tak terdefinisi bila storage gagal); id tak dikenal tetap 404.
- `realtime._decode`: inisialisasi `payload` eksplisit + guard `not payload`.
- `products_weight_guidance` dipecah → helper `_weight_guidance_item(p)` (kompleksitas turun, perilaku identik).
- Frontend: `src/lib/log.js` (`devWarn`, hanya aktif di dev) dipakai di catch yang sebelumnya membisu — `offline.js` (read/write/cacheCatalog/readCatalog), `RealtimeContext` (connect/onmessage/pong/close), `AuthContext` (cache user).
- SENGAJA TIDAK diubah (dengan alasan): token di localStorage (wajib agar sesi kasir bertahan saat OFFLINE & reload PWA — ganti ke httpOnly cookie = rework auth, perlu izin user); penambahan dependency hook secara buta (WebSocket/FLUSH_MS/api/e/r = false positive, berisiko reconnect & polling berulang); `random` di `seed.py` (data demo, bukan nilai keamanan); refactor kompleksitas `daily_closing_pdf`/`seed_demo`/`Layout` (kosmetik, tanpa nilai untuk user); jumlah argumen `record_movement`/`apply_stock` (menyentuh banyak call site, risiko > manfaat).
- Teruji: backend regresi **7/7 PASS** (weight-guidance identik, 4 endpoint PDF valid %PDF-, files 404, WS token invalid ditolak, regresi inti 11/11), frontend **7/7 PASS** (sesi bertahan, LIVE aktif, RBAC kasir, 0 error konsol, 0 warning `[bam]`).

## Code review hardening ronde 2 (2026-08-29)
- `pdf_reports.rp/num`: variabel diinisialisasi sebelum `try`; `tgl/tgl_singkat` pakai pola `d = None` + guard → tidak ada jalur kode yang menyentuh variabel belum terdefinisi.
- `server.py`: variabel comprehension `payable_outstanding` (`p` → `pay`) agar tidak menyamarkan variabel luar; angka terbukti tidak berubah.
- `POS.js`: ternary bersarang satuan diganti lookup level modul — `UNIT_INPUT_LABEL`, `UNIT_BUTTON_LABEL`, `priceOf`, `modalOf`, `primaryUnit`, `qtyLabel`. `Products.js`: helper `pickWeight()` + `weightNote()`.
- False positive yang dikonfirmasi: temuan "`is` vs `==`" semuanya `is None`/`is not None`/`is False` (pemakaian benar); temuan "missing hook deps" — build CRA menjalankan `react-hooks/exhaustive-deps` dan 25 kompilasi terakhir **0 warning**.
- Teruji: backend **G1-G5 PASS** (4 PDF valid, payable_outstanding sama dengan total hutang, weight-guidance identik, regresi inti 11/11) + frontend **H1-H9 PASS** (harga kartu, label satuan, keranjang kg/ekor/pcs, transaksi tunai Rp 84.000, RBAC modal, panel berat, 0 error konsol).

## Environment restore (2026-08-29, sesi lanjutan)
- Repo `shezrofenia18-ship-it/Project1` sudah tersambung; branch lokal `conflict_290826_1811` = `origin/main` untuk seluruh kode (hanya beda 1 commit auto-generated `90b9033` yang mengubah file infra `.emergent/emergent.yml`, bukan kode aplikasi). Tidak ada perubahan kode yang hilang.
- Dependencies diinstall ulang: pip `requirements.txt` (exit 0) + `yarn install` (exit 0). backend & frontend RUNNING via supervisor, mongodb RUNNING.
- Verifikasi live preview: login owner → Dashboard Owner tampil dengan data nyata (omzet Rp 3.743.030, 14 transaksi, 65,51 kg, margin 19,06%), indikator ONLINE + LIVE (WebSocket) aktif, grafik 7 hari & aktivitas terisi. DB utuh: 14 produk, 73 penjualan, 5 user.
- `memory/test_credentials.md` dibuat ulang (5 akun: owner/admin/kasir).

## Implemented (2026-08-29 — Grafik Bulanan, Struk Termal 58mm, & Perbaikan Sinkronisasi Data)

### Rumus keuangan tunggal (`backend/finance.py`) — keputusan owner: "Cara 2"
- `Laba Kotor` = Omzet − HPP · `Biaya Operasional` = pengeluaran KECUALI kategori modal ("Pembelian Ayam", "Pembayaran Hutang") · `Laba Bersih Usaha` = Laba Kotor − Biaya Operasional.
- `Kas Masuk` = seluruh pemasukan · `Kas Keluar` = biaya operasional + uang yang BENAR-BENAR dibayar untuk ayam/hutang (`cash_amount`) · `Uang Bersih (Kas)` = Kas Masuk − Kas Keluar.
- Biaya beli ayam ikut dihitung di jalur KAS (permintaan owner) tanpa dikurangi dua kali dari laba (sudah ada di HPP). Dipakai bersama oleh `/api/dashboard`, `/api/reports/profit-loss`, dan tutup buku → angka tidak bisa lagi berbeda antar halaman.

### 10 penyebab data tidak sinkron yang ditutup
1. Dashboard mengurangi SEMUA pengeluaran (termasuk beli ayam) sedangkan Laporan/Tutup Buku tidak → kini satu rumus.
2. Pembelian Rp 4.640.000 (27 Agu) tidak punya catatan pengeluaran & `supplier.total_purchase` = 0 → dibuat + saldo direkalkulasi.
3. 3 penjualan kurang bayar milik "Umum" mencatat piutang tanpa dokumen tagihan (selisih Rp 242.536 antara Riwayat & Keuangan) → `create_sale` kini SELALU membuat tagihan bila `receivable > 0`.
4. `cancel_sale` meninggalkan piutang "hantu" → tagihan ditandai "batal" + saldo pelanggan dikoreksi.
5. Pelunasan piutang tidak memperbarui dokumen penjualan → `pay_receivable` menyetel `sale.receivable` & `payment_status` ("lunas"). `sale.paid` sengaja tetap (= nilai catatan pemasukan) agar kas tidak dobel.
6. `pay_receivable`/`pay_payable` tanpa validasi → 0/negatif/melebihi sisa/sudah lunas → 400.
7. Pembelian kredit dicatat penuh lalu pelunasan dicatat lagi → kas keluar dobel → dipisah `amount` (modal) vs `cash_amount` (kas).
8. Tidak ada `rt_emit` pada pembelian, pembayaran piutang/hutang, penyesuaian stok → ditambahkan (+ topik incomes/customers/suppliers/purchases/payables).
9. Halaman Keuangan, Riwayat, Pembelian, Laporan, Pelanggan, Supplier tidak berlangganan realtime → sekarang ikut segar otomatis.
10. "Pembelian Ayam" ada di dropdown pengeluaran manual (pengeluaran jadi luput dari laba) → dihapus dari `EXP_CATS`.

### Rekonsiliasi otomatis (`backend/reconcile.py`)
- 7 invarian diperiksa/diperbaiki, IDEMPOTEN, jalan otomatis saat startup + `GET /api/maintenance/consistency` (owner/admin) & `POST /api/maintenance/reconcile` (owner) → tombol "Periksa Data"/"Perbaiki Sekarang" di Pengaturan.

### Grafik tren bulanan
- `GET /api/dashboard/monthly?months=N` (clamp 1..36). Dashboard: toggle `7 Hari / Bulanan` + dropdown 3/6/12/24 bulan, batang Omzet + garis Laba Kotor & Laba Bersih, ringkasan pertumbuhan vs bulan lalu / bulan terbaik / rata-rata / total. Kartu baru "Uang Masuk & Keluar Hari Ini"; blok arus kas di Laporan & Tutup Buku.

### Struk termal 58mm
- `@page { size: 58mm auto; margin: 0 }`, body 58mm, Courier 11px, ruang sobek 10mm. Cetak lewat IFRAME tersembunyi (bebas pemblokir popup) → mendukung cetak otomatis; fallback `window.open`.
- Setting `receipt_auto_print` (Pengaturan) + tombol "Tes Cetak Struk". Terverifikasi: transaksi POS Rp 14.000 → 1 iframe (tidak dobel), lebar body 219,203px = tepat 58mm, iframe dibersihkan otomatis.

### RBAC
- Menu & rute **Pembelian** dihapus dari kasir (nav, `/pembelian` redirect ke `/pos`, `GET /api/purchases` owner/admin saja). `useFetch` tidak lagi memanggil API bila path null → hilang 404 palsu di konsol kasir.

### Teruji
- Backend **58/58 PASS**, `issue_count = 0` sebelum & sesudah seluruh rangkaian uji. Frontend **29/30 PASS**; satu sisa (cetak otomatis pasca-transaksi) diverifikasi manual oleh main agent. Transaksi uji dibatalkan, saklar cetak otomatis dikembalikan MATI.

### Tindak lanjut code review (2026-08-29, ronde 3)
- **Diterapkan**: `reconcile.audit()` dipecah (kompleksitas 65 → maks **9**, 198 → maks **25 baris**, nesting 5 → 2) memakai kelas `_Audit` + 7 fungsi pemeriksa + tuple `CHECKS`; perilaku identik, dibuktikan dengan uji perusakan data untuk **12/12** jenis temuan (23/23 tes lolos). `lib/receipt.js`: 2 `catch` tidak lagi menelan error (devWarn + toast "Cetak struk gagal").
- **Temuan PALSU (diverifikasi, tidak ada yang perlu diubah)**: (a) "20 pemakaian `is` untuk membandingkan nilai" → nyatanya **0**; semua adalah `is None`/`is not None`/`is False` yang justru benar secara Python. (b) "console statement bocor di produksi" → ketiganya sudah dibungkus `process.env.NODE_ENV !== "production"` (`lib/log.js`, `hooks.js`, `OwnerDashboard.js`). (c) "hook dependency hilang" → build CRA (eslint `react-hooks/exhaustive-deps`) **0 warning**; dependensi yang disebut (`WebSocket`, `FLUSH_MS`, `api`, `apiError`, `e`) adalah konstanta modul/import/variabel `catch` yang memang TIDAK boleh masuk dep array.
- **Sengaja TIDAK diubah (dengan alasan)**: token di `localStorage` (wajib agar kasir tetap bisa transaksi offline & untuk auth WebSocket; httpOnly cookie akan mematikan mode offline — perubahan arsitektur auth harus dengan persetujuan owner). `random` di `seed.py` hanya membuat data demo, bukan rahasia keamanan. Refactor `pdf_reports.py`, `seed_demo()`, `Layout.js`, `RealtimeContext.js`, `PendingSales.js` ditunda: kode berjalan & teruji, tanpa manfaat yang terlihat owner, sedangkan risiko regresinya nyata.

## Environment restore (2026-08-29, sesi lanjutan #3)
- Repo `shezrofenia18-ship-it/Project1` tersambung (remote `origin` sudah ada). Branch aktif `conflict_290826_1811` = **8 commit di depan `origin/main`** dan hanya 1 commit di belakang (`90b9033`, auto-generated file infra). Jadi SELURUH pekerjaan terbaru ada di workspace: Grafik Bulanan + Struk Termal 58mm + Perbaikan Sinkronisasi Data (`3b30688`) dan Tindak Lanjut Code Review / refactor `reconcile.audit()` (`4519406`).
- Dependencies diinstall ulang: pip `requirements.txt` (reportlab 5.0.1, exit 0) + `yarn install` (945 paket, exit 0 — `node_modules` sebelumnya kosong).
- backend & frontend RUNNING via supervisor (mongodb RUNNING). Frontend "Compiled successfully", 0 error konsol.
- Rekonsiliasi otomatis di startup terbukti idempoten: startup ke-1 memperbaiki 5 hal (piutang_tanpa_tagihan=3, pembelian_tanpa_pengeluaran=1, saldo_supplier=1), startup ke-2 = 0 perbaikan.
- Verifikasi live preview: login owner → Dashboard Owner tampil data nyata (omzet Rp 3.743.030 · 14 transaksi · 65,51 kg · laba kotor Rp 713.595 · margin 19,06% · Uang Bersih Kas Rp 3.427.038), badge ONLINE + LIVE aktif, toggle `7 Hari / Bulanan` ada, grafik & aktivitas terisi.
- DB utuh: 5 user, 14 produk, 73 penjualan, 1 pembelian, 5 pelanggan, 3 supplier, 29 pengeluaran.
- `memory/test_credentials.md` dibuat ulang (5 akun: 2 owner, 1 admin, 2 kasir).
- CATATAN KEAMANAN: user kembali menempel GitHub PAT di chat → PAT tersebut harus DI-REVOKE.

## Perubahan sesi #4 (30 Agu 2026) — 5 permintaan owner

### 1. Jual per ekor memotong stok KG (perhitungan jadi terukur)
- MASALAH: pembelian menambah stok ekor DAN kg, tapi `create_sale` hanya mengurangi `stock_ekor`
  (`d_kg = -qty if unit == "kg" else 0`). Stok kg ayam utuh tidak pernah berkurang.
- SEKARANG: jual 1 ekor -> `stock_ekor -1` DAN `stock_kg -= berat rata-rata/ekor`. Berat yang dipakai
  DISIMPAN di baris penjualan (`items[].weight_kg`, `items[].avg_weight_used`) supaya pembatalan
  mengembalikan angka yang sama walau berat rata-rata sudah berubah karena pembelian baru.
- Dokumen penjualan: `total_weight` = item per-kg + konversi item per-ekor, plus
  `total_weight_kg_unit` & `total_weight_ekor` untuk penelusuran. Transaksi LAMA tidak berubah
  (fallback `weight_kg` = qty untuk unit kg, 0 untuk unit ekor).
- Berat rata-rata/ekor tetap KUMULATIF seluruh pembelian (keputusan owner) + override manual.
- Form Pembelian kini menampilkan hasil hitungnya langsung: "Berat 1 ekor kiriman ini: 2 kg/ekor"
  (2 ekor / 4 kg) beserta baris ringkasan "Berat rata-rata/ekor kiriman ini".

### 2. Ayam utuh HANYA dijual per ekor
- `is_whole_chicken(p)` = "ekor" ada di `p.units` -> Ayam Broiler, Kampung, Pejantan.
- POS: `posUnits()` memangkas pilihan jadi ["ekor"] sehingga tombol "Per Kg" hilang untuk SEMUA role.
- Server ikut mengunci: jual unit "kg" untuk produk itu -> 400 "hanya bisa dijual per ekor".
- TIDAK berubah: Fillet (kg), potongan & sampingan (kg + pcs).

### 3. Keranjang POS di Tablet & HP (bug dilaporkan owner) — 2 bug ditemukan
- BUG A (tata letak): wadah tinggi tetap + kolom produk `flex-1` mendorong keranjang keluar layar di
  bawah 1024px (termasuk TABLET yang justru dipakai kasir). Diganti: bar tetap di bawah
  (jumlah item + total + "Lihat Keranjang") yang membuka panel geser berisi keranjang lengkap.
  Keranjang dirender HANYA SEKALI lewat `useIsDesktop()` supaya tidak ada elemen ganda di DOM.
- BUG B (lebih halus, ditemukan saat pengujian): ada TIGA salinan
  `@radix-ui/react-dismissable-layer` (1.1.7 dari react-dialog; 1.1.19 dari cmdk & vaul). Karena
  tidak berbagi React context, `pointer-events: none` yang dipasang di `<body>` saat dialog terbuka
  TIDAK selalu dibersihkan saat dialog ditutup -> sentuhan berikutnya di layar terabaikan TANPA
  error apa pun (tombol terasa "mati"). Diperbaiki dengan `hooks/usePointerEventsGuard.js`
  (MutationObserver pada style `<body>` + cek berkala 250ms, hanya membersihkan bila memang tidak
  ada lapisan Radix yang terbuka), dipasang sekali di `App.js` sehingga melindungi SEMUA dialog.
  Bar bawah juga sudah menghormati `env(safe-area-inset-bottom)` untuk HP berponi.

### 4. Metode pembayaran piutang & hutang
- `PayBody.method` (cash/transfer/qris/debit/ewallet, default cash; lain -> 400). Tersimpan di
  dokumen income "Pembayaran Piutang" / expense "Pembayaran Hutang", array `payments`, dan
  `last_method` pada tagihan. Rumus keuangan (finance.py) TIDAK diubah.
- UI: komponen `PayMethodPicker` (tombol besar berikon, nyaman di tablet), kolom "Metode" di tabel
  Piutang & Hutang, bagian baru "Pelunasan Piutang & Hutang per Metode Bayar" di Tutup Buku dan
  bagian "C2" di PDF tutup buku.

### 5. Foto bukti pengeluaran + "Salah Potong"
- `POST /api/upload` kini menerima role kasir juga, dengan Form field `folder`
  ("products"/"proofs"); role kasir DIPAKSA ke "proofs". Batas 10 MB.
- `ExpenseBody.proof_file_id` & `proof_url` (opsional). UI: input `capture="environment"`
  (langsung kamera di HP), pratinjau, tombol hapus foto, kolom "Bukti" berisi thumbnail yang bila
  diklik membuka gambar penuh.
- Penyesuaian stok: pilihan "Ayam Mati" diganti "Salah Potong" (`salah_potong`). Whitelist
  `ADJUST_TYPES` di server; nilai "mati" dipertahankan agar riwayat lama tetap terbaca.

### Catatan pemeliharaan
- `backend/cleanup_test_data.py`: pembersih artefak data uji. Memulihkan stok dari jumlah delta
  `stock_movements` (bukan angka hafalan), membatalkan pembayaran uji pada tagihan lama, dan
  menghitung ulang akumulator berat/ekor dari pembelian yang tersisa. Punya mode simulasi.

## Test Credentials
Lihat `/app/memory/test_credentials.md`.

## Environment restore (2026-08-29, sesi #5)
- Repo `shezrofenia18-ship-it/Project1` tersambung. Branch kerja aktif = `conflict_290826_1811`
  (tip `c465491`, 29 Agu 18:03) = identik dengan `origin/conflict_290826_1811`. Semua 11 commit
  sesi terakhir AMAN di remote. `origin/main` masih tertinggal (tip `90b9033`, 29 Agu 11:12).
- Dependencies diinstal ulang: pip requirements.txt (reportlab naik ke 5.0.1 — generator PDF
  diverifikasi masih OK) + `yarn install` (node_modules sebelumnya kosong).
- backend & frontend RUNNING. Login owner → Dashboard Owner tampil dengan data (omzet Rp 3.743.030,
  65,51 kg, margin 19,06%), badge ONLINE + LIVE (WebSocket tersambung).
- `memory/test_credentials.md` dibuat ulang (sempat hilang lagi).

## Implemented (2026-08-30 — Rekap Tutup Buku Otomatis ke WhatsApp, Meta Cloud API)
Keputusan owner: provider **Meta WhatsApp Cloud API**, isi pesan **RINGKAS lewat template**
(omzet, laba bersih, jumlah transaksi) + PDF lengkap tetap diunduh di app. Penerima
081289478221 (fitur tambah nomor tetap ada), jam kirim **15:00 WIB**.
Kredensial Meta BELUM ADA (owner masih membuat akun WhatsApp Business) -> semua jalur wajib
tetap hidup dalam mode fallback wa.me 1-tap.

- `backend/whatsapp.py`: Graph API di-PIN **v26.0** (dari v25.0). Template UTILITY
  `rekap_tutup_buku_harian` (lang id, `parameter_format` NAMED) 4 parameter named:
  tanggal, omzet, laba_bersih, jumlah_transaksi. `send_template()` memakai `parameter_name`
  + `recipient_type: individual`; mendukung positional lewat env WA_TEMPLATE_PARAM_FORMAT.
- Kelas `WaError` + klasifikasi kode Meta: PERMANENT (131026, 132000, 132001, 132015, 132016,
  190, 0, …) TIDAK di-retry; TRANSIENT (130429, 131056, 5xx) di-retry 2x backoff 1.5s->3.75s.
  `ERROR_HINTS` menjelaskan tiap error dalam Bahasa Indonesia. Token tidak pernah masuk log.
- `send_closing()` berlapis: template -> teks biasa (bila template belum disetujui) -> wa.me
  1-tap. Tidak pernah melempar exception, jadi tutup buku tak bisa gagal karena WhatsApp.
- Fungsi baru: `create_template()`, `list_templates()`, `phone_status()`, `template_spec()`,
  `template_values()`.
- `backend/server.py` endpoint baru: `GET/POST /api/whatsapp/template`,
  `GET /api/whatsapp/diagnostics` (checklist 5 syarat + `ready_for_auto`),
  `GET/POST /api/whatsapp/webhook` (status sent/delivered/read/failed, upsert idempoten ke
  `wa_statuses`, cermin ke `wa_logs.results.$.status`, selalu 200), `GET /api/whatsapp/statuses`.
  `GET /api/whatsapp/settings` kini mengembalikan `template_spec`. `POST /api/whatsapp/test`
  menguji jalur template lebih dulu (jalur yang sama dengan rekap malam).
- **BUG DIPERBAIKI** pada `auto_closing_worker`: dulu `now.strftime("%H:%M") != target -> continue`,
  jadi rekap HILANG bila backend restart tepat di menit target. Sekarang "sudah melewati jam
  target" + catch-up, anti-dobel via `last_done` & `wa_sent_at`/`wa_attempt_at`.
- `backend/.env` menerima kunci baru (kosong, menunggu owner): META_PHONE_NUMBER_ID,
  META_ACCESS_TOKEN, META_WABA_ID, META_API_VERSION=v26.0, WA_TEMPLATE_NAME,
  WA_TEMPLATE_LANG, WA_TEMPLATE_PARAM_FORMAT, WA_WEBHOOK_VERIFY_TOKEN (dibuat acak).
- Frontend `pages/Settings.js`: komponen `WhatsAppActivation` — checklist 5 syarat berwarna,
  badge "Siap otomatis / Belum siap", tombol Periksa Kesiapan, **Buat Template di Meta** (1 klik
  submit ke Meta), panduan 5 langkah, pratinjau + copy isi template & payload JSON, URL webhook
  + copy. Riwayat pengiriman kini menampilkan status per nomor (terkirim/sampai/dibaca/gagal)
  beserta saran perbaikan. `pages/Closing.js`: pratinjau isi template ringkas + label jalur
  kirim (template/teks) per penerima.
- Teruji: backend **9/9 PASS** (fallback manual, RBAC, normalisasi nomor, multi nomor, validasi
  jam, webhook idempoten & 403 token salah, PDF tidak regresi). Penjadwal diuji nyata dengan
  menggeser jam ke +1 menit: log "Tutup buku otomatis dijalankan (jadwal 01:34 WIB)", snapshot
  benar (omzet 3.743.030, laba bersih 443.595, 14 transaksi). Artefak uji dihapus, jam
  dipulihkan ke 15:00.
- SISA UNTUK AKTIF PENUH (butuh owner): META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_WABA_ID
  lalu tekan "Buat Template di Meta" dan tunggu status APPROVED.

## Implemented (2026-08-30 — Lampiran PDF Laporan Penjualan pada rekap WhatsApp)
Permintaan owner: "kirimkan saja beserta PDF Laporan penjualan".
Kendala aturan Meta: template body-only yang sudah dibuat TIDAK bisa diberi lampiran saat
kirim -> lampiran wajib template TERPISAH berheader DOCUMENT + contoh media saat pembuatan.

- Template kedua `rekap_tutup_buku_pdf` (HEADER DOCUMENT + 4 parameter body yang sama).
  Contoh media diunggah lewat Resumable Upload API (`/{META_APP_ID}/uploads` lalu
  `/upload:<sesi>` header `file_offset`, skema Authorization "OAuth").
- PDF aktual diunggah ke `POST /{phone_id}/media` (media ID berlaku 30 hari, dipakai ulang
  untuk semua penerima) lalu dikirim sebagai header dokumen `{id, filename}` (tanpa caption).
- `send_closing()` berlapis 5: template+PDF -> template ringkas -> dokumen+caption -> teks ->
  wa.me 1-tap. Error permanen (131026/190/0) memutus percobaan lanjutan.
- Karena wa.me tidak bisa melampirkan file, dibuat TAUTAN PDF PUBLIK ber-token:
  koleksi `share_links` (token 43 karakter, kedaluwarsa 30 hari, penghitung hits) +
  `GET /api/public/laporan/{token}` tanpa auth (404 token salah, 410 kedaluwarsa). Tautan ini
  otomatis disisipkan di teks rekap: blok "*PDF Laporan Penjualan:*".
- URL publik TIDAK di-hardcode: middleware `capture_public_base` merekam skema+host dari
  header x-forwarded-* permintaan pertama ke `settings.public_base_url`; `_public_base_url()`
  berurutan env PUBLIC_BASE_URL -> settings -> REACT_APP_BACKEND_URL di frontend/.env.
- Setting `wa_attach_pdf` (default ON) bisa dimatikan owner dari Pengaturan.
- UI: sakelar "Lampirkan PDF Laporan Penjualan", 2 baris checklist baru (template berlampiran +
  PDF siap), tombol "Buat Template Ringkas" & "Buat Template + PDF", copy payload versi PDF.
  Dialog Tutup Buku: baris "PDF Laporan Penjualan" + tombol Buka PDF, label jalur kirim.
- Teruji: backend **10/10 PASS**. PDF laporan penjualan 4.845–5.947 byte, tautan publik
  terbukti bisa diunduh TANPA login (200, application/pdf, header %PDF), token ngawur -> 404,
  attach_pdf=false -> pdf_url kosong. Tidak ada regresi PDF/dashboard/penjualan.
  Diverifikasi visual: dialog Tutup Buku menampilkan baris PDF + tautan ada di teks rekap.
- SISA UNTUK AKTIF PENUH: META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_WABA_ID, META_APP_ID.

## Tindak lanjut Code Review (2026-08-30)
Dari 8 kategori temuan, **2 valid (diterapkan)** dan **6 FALSE POSITIVE (dibuktikan, tidak diubah)**:

DITERAPKAN:
1. `server.py` — pola `res` dibuat tak-ambigu: `create_wa_template()` menginisialisasi
   `res: dict = {}` sebelum try + guard `isinstance` + `except Exception` -> 502 khusus
   kegagalan menghubungi Meta (kredensial kosong TETAP 400). `send_wa_test()` juga
   menginisialisasi `res: dict = {}` per penerima.
2. `frontend/src/pages/Settings.js` — baris riwayat pengiriman diekstrak ke komponen
   `WaLogRow` + `useMemo` (penyaringan status & pencarian error tidak lagi dihitung di JSX
   setiap render induk). Bentuk respons API tidak berubah.

FALSE POSITIVE (bukti, bukan asumsi):
- `is` vs `==` (23 temuan): SEMUA berbentuk `is None` / `is not None` / `is False` = idiom
  BENAR menurut PEP 8. `grep "is \"literal\""` = 0 hasil. Mengubahnya justru regresi.
- React hook deps (34 temuan): dijalankan dengan eslint-plugin-react-hooks 5.2.0 asli
  (exhaustive-deps + rules-of-hooks) atas 46 file `src/` -> **0 warning, 0 error**. Daftar
  "dependensi hilang" berisi nilai STABIL (import `api`/`apiError`, global `WebSocket`,
  setter `setPrice`) yang bila dimasukkan ke deps akan memicu loop render/reconnect.
- Console statements: seluruhnya sudah dipagari `process.env.NODE_ENV !== "production"`
  (lib/log.js, lib/hooks.js, RealtimeContext.js, Layout.js, SalesTrendCard.js).
- `seed.py` random -> secrets: `random` hanya untuk variasi DATA DEMO, bukan token/ID rahasia.
  Randomness sensitif satu-satunya (token tautan PDF) memang sudah `secrets.token_urlsafe(32)`.
- localStorage -> httpOnly cookie: DITOLAK karena akan merusak Mode Offline POS (sesi kasir
  wajib bertahan saat offline & reload — bug yang sudah diperbaiki di FASE 1). Selain itu
  aplikasi TIDAK punya sink XSS (`dangerouslySetInnerHTML`/`innerHTML`/`eval` = 0 hasil).
- Refactor kompleksitas `create_sale()` (38) & `dashboard()` (23): DITUNDA. Keduanya jalur uang
  & angka bisnis yang butuh berkali-kali sesi untuk benar; refactor demi metrik tanpa manfaat
  terlihat berisiko regresi. Ditawarkan ke owner sebagai tugas terpisah dengan uji penuh.

Teruji: backend **55/55 PASS** (termasuk pemastian kredensial kosong tetap 400 bukan 500/502,
bentuk data /whatsapp/log tidak berubah, tautan PDF publik, semua PDF, penjualan+pembatalan,
webhook idempoten, RBAC). Artefak uji dibersihkan; setting dipulihkan (15:00, attach_pdf ON).

## Environment restore (2026-08-30 — sesi lanjutan)
- Repo `shezrofenia18-ship-it/Project2` sudah tersambung; `git fetch` menunjukkan local `main` == `origin/main` (HEAD `0e8607e`, 0 ahead / 0 behind) — tidak ada commit remote yang tertinggal. 15 commit terakhir diverifikasi (terbaru: "Auto-generated changes" 30/08 09:47, sebelumnya "## 3 Permintaan Selesai & Teruji", "## 5 Permintaan Selesai & Teruji").
- Dependencies diinstall ulang: pip `requirements.txt` (reportlab naik ke 5.0.1 — PDF tetap valid) + `yarn install` (node_modules sempat hilang total, selesai 37s).
- backend & frontend RUNNING via supervisor. Verifikasi: login owner 200 (token 236 char), `/api/dashboard` 200, `/api/reports/profit-loss/pdf` 200 (3.461 byte, header %PDF). Frontend "Compiled successfully", port 3000 = 200.
- Live preview diverifikasi visual: halaman Masuk tampil, login owner → Dashboard Owner dengan data nyata (omzet Rp 3.358.010 / 14 transaksi, 56,9 kg, laba kotor Rp 683.475, margin 20,35%, grafik 7 hari, performa produk, aktivitas toko).
- `memory/test_credentials.md` dibuat ulang (sempat hilang lagi) berisi owner utama + 4 akun demo seed.

## Tindak lanjut Code Review "Environment 7637b074" (2026-08-30)
Laporan ini ~90% mengulang review sebelumnya. Diverifikasi ulang dengan BUKTI, bukan asumsi:
**3 DITERAPKAN, sisanya FALSE POSITIVE (ditolak dengan bukti).**

DITERAPKAN:
1. `maintenance.py::_parse()` — `dt = None` sebelum try, `except (ValueError, TypeError,
   OverflowError)`, guard `if dt is None`. Catatan: `dt` sebetulnya SUDAH selalu terikat
   (jalur except melakukan `return`), jadi klaim "used before assignment" tidak akurat; tapi
   modul ini jalan saat STARTUP backend sehingga ketahanan terhadap `created_at` rusak berharga.
2. `maintenance.py::_collect_future()` — `_parse` tadinya dipanggil DUA KALI per dokumen
   (hingga 20.000 dok/koleksi) + mencampur `r.get("created_at")` dengan `r["created_at"]`.
   Kini satu kali parse via loop, `ts is not None and ts > now`. Perilaku tak berubah.
3. `frontend/src/pages/POS.js` — 2 blok catch localStorage (ukuran kartu POS) kini memakai
   `devWarn` dari `src/lib/log.js` (sunyi di produksi). SENGAJA TIDAK memakai toast ke pengguna
   seperti disarankan review: gagal simpan preferensi tampilan bukan gangguan transaksi.

FALSE POSITIVE (dibuktikan):
- **39 "missing hook dependencies"**: dijalankan eslint 9.23.0 + eslint-plugin-react-hooks 5.2.0
  ASLI (exhaustive-deps + rules-of-hooks + no-empty allowEmptyCatch:false) atas seluruh `src/`
  (92 entri file) -> **0 warning, 0 error**. Saran-sarannya tidak masuk akal: `localStorage`
  (global browser, non-reaktif), `id` (variabel yang DIBUAT di dalam effect), `i`/`s`/`e`/`r`
  (parameter callback reduce/map), `api`/`apiError`/`priceOf` (import level-modul, stabil).
  Contoh POS.js:528 `[unit, priceFor]` sudah lengkap. Menambahkannya = loop render.
- **24 "`is` vs `==`"**: hitung nyata 21 (`server.py` 7, `auth.py` 5, `reconcile.py` 4,
  `pdf_reports.py` 3, `finance.py` 2, `maintenance.py` 0 — bukan 24). SEMUA berbentuk
  `is None`/`is not None`/`is False` = idiom PEP 8 BENAR. `grep 'is +["\x270-9]'` = 0 hasil.
  Mengubah `body.active is not None` -> `==` justru MERUSAK penonaktifan pengguna.
- **localStorage -> httpOnly cookie**: ditolak (sama seperti sesi lalu) karena merusak Mode
  Offline POS (sesi kasir wajib bertahan offline+reload — bug yang sudah diperbaiki di FASE 1).
  `POS.js:81` menyimpan preferensi UKURAN KARTU, bukan data sensitif. Sink XSS di `src/`
  (`dangerouslySetInnerHTML`/`innerHTML`/`eval`) = **0 hasil**.
- **"POS.js:138 empty catch"**: blok berisi komentar; eslint `no-empty` = 0 warning. Tetap
  ditambah logging (butir 3 di atas) karena logging-nya memang belum ada.
- **Refactor kompleksitas** `create_sale()` 38 / `dashboard()` 23 / `cleanup_test_data.main()` 31
  dll: TETAP DITUNDA. Jalur uang & angka bisnis; refactor demi metrik tanpa manfaat terlihat
  berisiko regresi. Ditawarkan sebagai tugas terpisah dengan uji penuh.

Teruji (testing agent, backend **6/6 PASS**, 0 regresi): startup bersih tanpa traceback;
**IDEMPOTENSI** restart backend tidak menggeser `created_at` (5 penjualan, identik hingga
mikrodetik); tidak ada dokumen bertanggal masa depan (10 penjualan); PDF laba-rugi 3.461 B /
penjualan 13.733 B / stok 3.998 B semua %PDF; idempotency txn_id (POST 2x -> sale_id sama,
stok 120->119 ekor tidak dobel, pemasukan 1 entry) & cancel memulihkan stok ke 120 ekor/225,50 kg;
RBAC utuh (admin & kasir login 200, endpoint owner 403). Artefak uji dibersihkan.

## Refactor jalur uang: create_sale() & dashboard() (2026-08-30, diminta owner)
Sebelumnya ditunda karena berisiko; owner meminta dikerjakan dengan uji penuh. Strategi:
ambil BASELINE output API dulu, refactor tanpa ubah perilaku, lalu bandingkan.

- `create_sale()` 115 baris / 28 variabel lokal -> orkestrator **26 baris** + 7 helper:
  `_sale_validate`, `_sale_line_out` (MURNI, tanpa DB), `_sale_collect_items`, `_sale_money`
  (MURNI), `_sale_document`, `_sale_apply_stock`, `_sale_record_side_effects`.
  Kompleksitas mccabe (flake8 C901): **17 -> 2**.
- `dashboard()` 74 baris -> orkestrator + 5 helper: `_dashboard_chart` (async),
  `_perf_by_category`, `_stock_overview`, `_price_highlights`, `_target_progress` (4 terakhir MURNI).
  Kompleksitas mccabe: **10 -> 1**.
- **PERBAIKAN KINERJA NYATA**: grafik 7 hari tadinya 7 QUERY TERPISAH ke MongoDB tiap dashboard
  dibuka, padahal frontend polling dashboard tiap 8 detik. Kini SATU query `$in` + kelompok di memori.
- ATURAN YANG DIJAGA: urutan operasi & SETIAP pembulatan disalin apa adanya. Stok tetap dipotong
  SEBELUM dokumen penjualan disimpan (supaya penjaga stok membatalkan transaksi sebelum uang tercatat).

Catatan angka review vs alat standar: review menyebut create_sale 38 & dashboard 23; mccabe
(flake8) menunjukkan 17 & 10 sebelum refactor. Angka review konsisten ~2x lebih tinggi.

VERIFIKASI:
- Perbandingan output `/api/dashboard` sebelum vs sesudah: **26 dari 27 kunci IDENTIK**.
  Satu-satunya beda `stock_value` (12.894.896,73 -> 12.696.896,73) TERBUKTI bukan dari refactor:
  audit_logs menunjukkan 2 aksi `update` produk "Ati Ampela" oleh pengguna lewat UI (18:06:28 &
  18:08:05 WIB; units ['kg','pcs']->['pcs'], hpp_kg 18000->0, price_kg 28000->0, price_pcs 4000->2000).
  Rumus LAMA & BARU dijalankan atas data yang SAMA -> hasil identik (12.696.896,73), dan
  12.894.896,73 - 198.000 = 12.696.896,73 tepat. `/api/reports/profit-loss` identik 100%.
- Testing agent: **18/18 PASS**. Jual per ekor/kg/pcs; kunci ayam-utuh (unit kg -> 400);
  validasi keranjang kosong & piutang tanpa pelanggan (400); produk tak ada (404); diskon &
  kembalian; piutang + tagihan + saldo pelanggan; kekurangan bayar non-piutang tetap bikin tagihan;
  idempotensi txn_id (sale_id sama, stok & pemasukan tidak dobel); penjualan offline
  (created_at=offline_at, synced_at, aktivitas "Penjualan Offline Tersinkron"); notifikasi
  Transaksi Besar >= 1 jt; pembatalan memulihkan stok PERSIS; penjaga stok negatif (400);
  dashboard 27 kunci; chart 7 entri urut & omzet hari ini cocok; products_perf terurut menurun;
  PDF semua 200/%PDF; RBAC kasir -> dashboard 403.
  Stok awal == akhir: Broiler 155 ekor/285,01 kg, Fillet 24,70 kg, Ceker 120 pcs. Artefak dibersihkan.
- Diverifikasi visual di live preview: Dashboard Owner normal (omzet Rp 3.345.610, 15 transaksi,
  grafik 7 hari, Performa Produk, Target). POS: 14 kartu produk, dialog entry, "+" stepper,
  "Tambah ke Keranjang" -> toast + keranjang 1 item Rp 55.000, catatan "Stok berkurang 1,75 kg
  (1 ekor x 1,75 kg/ekor)".
- CATATAN: laporan testing agent frontend sebelumnya menyebut "Tambah ke Keranjang timeout" —
  BUKAN bug: qty masih 0 karena satuan pcs/ekor memakai stepper +/- (bukan keypad angka).
  Dibuktikan berfungsi normal setelah menekan "+".

## Keypad Ekor + Manajemen Pengguna + LOGIN PINDAH KE USERNAME (2026-08-30, permintaan owner)

### 1. POS: keypad untuk satuan EKOR & PCS (`frontend/src/pages/POS.js`)
Keluhan owner: "10 ekor = 10 kali tekan tombol plus". Dulu keypad HANYA tampil untuk kg.
Sekarang keypad tampil untuk SEMUA satuan; tombol +/- TETAP ada (pilihan owner: keduanya).
kg -> `KEYPAD_DECIMAL` [1-9, ",", 0, del]. ekor/pcs -> `KEYPAD_INTEGER` [1-9, "C", 0, del]
("C" = hapus semua, karena ekor & pcs selalu bilangan bulat). Input `entry-qty` menolak
titik/koma untuk ekor/pcs (inputMode numeric). Stepper diberi testid `qty-minus`/`qty-plus`.

### 2. Manajemen pengguna: Ubah / Nonaktifkan / Hapus (`backend/auth.py`, `frontend/src/pages/Users.js`)
Pilihan owner: sediakan Nonaktifkan DAN Hapus permanen; boleh ubah nama/username/role/status/
kata sandi; tak boleh hapus akun sendiri & tak boleh sampai 0 owner aktif; HANYA Owner yang boleh.
- Endpoint BARU `DELETE /api/auth/users/{id}`. `PUT` diperkuat.
- **3 BUG LAMA ikut ketemu & diperbaiki di PUT**: id ngawur -> dulu **500**, kini 404;
  user tidak ada -> dulu **500**, kini 404; role TIDAK divalidasi di PUT (padahal POST validasi)
  -> kini 400 "Role tidak valid". Ditambah: nama kosong 400, kata sandi < 6 karakter 400.
- Owner utama (username = ADMIN_USERNAME) DILINDUNGI: tidak bisa dihapus/dinonaktifkan dan
  username-nya tidak bisa diubah dari UI, sebab `seed_admin()` membuatnya ulang setiap backend
  start (kalau tidak dilindungi akan tampak seperti bug "hapus tapi kembali").
- Semua update/delete dicatat ke `audit_logs` (entity "user") via `_audit_user()` — ditulis lokal
  karena auth.py tidak boleh mengimpor server.py (impor sirkular). Tanpa kebocoran password_hash.
- UI: kolom Aksi hanya untuk owner; baris akun sendiri bertanda "(Anda)" dengan tombol
  Nonaktifkan & Hapus dinonaktifkan; dialog dipakai ulang untuk Tambah & Ubah (kata sandi
  kosong = tidak diubah); dialog konfirmasi hapus menjelaskan riwayat transaksi tidak hilang.

### 3. LOGIN PINDAH DARI EMAIL KE USERNAME (perubahan besar)
Keputusan owner: username + kata sandi ditentukan owner; email DIHAPUS TOTAL; tanpa masa
transisi; username minimal 5 karakter tanpa spasi; `ADMIN_USERNAME=owner`.
- Model & JWT: `email` -> `username`. `get_current_user()` kini mencari user via `sub` (ID akun).
  **Ini sekaligus memperbaiki bug**: dulu dicari lewat email, sehingga owner yang mengganti
  email/username staf otomatis memutus sesi orang itu. Efek samping bagus: token lama tetap sah.
- `get_current_user()` juga menolak akun nonaktif (403) tanpa menunggu token kedaluwarsa.
- `realtime.py` identitas WS pakai username; `log_audit()` `user_email` -> `user_username`.
- **MIGRASI 3 TAHAP di startup, urutan WAJIB**: (1) `drop_legacy_email_index()` buang index unik
  `email_1`, (2) `migrate_usernames()` beri username dari bagian depan email lama lalu
  `$unset email`, (3) `ensure_user_indexes()` buat index unik `username`.
  KENAPA URUTAN INI: kalau `$unset email` jalan sementara `email_1` masih ada, semua email jadi
  null dan MongoDB melempar **E11000 dup key -> STARTUP BACKEND GAGAL TOTAL**. Ini SUDAH TERJADI
  saat pengembangan dan sudah diperbaiki.
- Owner utama diproses PALING AWAL agar memenangkan username "owner"; yang bentrok dapat sufiks
  angka -> `owner@berkahayam.com` menjadi `owner2`.
- **INSIDEN & PEMULIHAN**: reload perantara menjalankan migrasi SEBELUM ADMIN_USERNAME ada di
  .env, sehingga akun asli owner mendapat `shezrofenia18` lalu `seed_admin()` membuat akun
  `owner` BARU yang kosong (jadi 8 akun, 2 owner bernama sama). Diperiksa lewat jejak data
  (akun asli punya 20 penjualan, duplikat 0), duplikat kosong DIHAPUS, akun asli dipindah ke
  username `owner`. Hasil 7 akun; restart berikutnya terbukti idempoten.

### Akun setelah migrasi (lihat memory/test_credentials.md)
owner/berkahayam1 (owner, akun utama & dilindungi) · owner2/berkahayam1 (owner) ·
admin/admin123 · kasir/kasir123 · operator/operator123 (role kasir) ·
kinggacau & kingolive (staf NYATA milik owner, sandi ditentukan owner — JANGAN dihapus saat uji).

### Verifikasi
- Testing agent backend: manajemen pengguna **18/18 PASS**; migrasi username **25/25 PASS**
  (email 0 akun, index `username_1` unique & `email_1` hilang, restart idempoten 7 akun,
  token akun nonaktif langsung 403, RBAC utuh, audit `user_username`, regresi dashboard &
  penjualan+pembatalan stok 145->144->145).
- CATATAN: testing agent pernah melaporkan "audit logging tidak jalan" sebagai BUG KRITIS —
  diverifikasi langsung ke MongoDB dan KLAIM ITU SALAH (71 dokumen audit_logs, 18 entity=user,
  0 kebocoran password_hash). Tidak ada kode yang diubah.
- Diverifikasi visual di live preview: halaman Masuk berlabel "Username" (Email hilang), login
  `owner` -> Dashboard Owner (omzet Rp 4.090.610), halaman Pengguna menampilkan kolom Username +
  Aksi (Ubah/Nonaktifkan/Hapus), baris sendiri bertanda "(Anda)" dengan tombol destruktif mati.
- Frontend keypad/ukuran kartu diuji agent: 9/9 PASS (uji frontend untuk fitur ini diserahkan
  ke owner atas permintaannya).

## Environment restore (2026-09-03)
- Repo `shezrofenia18-ship-it/Project-Clone` tersambung; local `main` == `origin/main` (HEAD f50360d "Update requirements.txt"), git pull -> Already up to date.
- Dependencies diinstall ulang: pip -r backend/requirements.txt (reportlab sempat hilang) + yarn install 945 paket (perlu hapus node_modules/global-prefix karena error EEXIST symlink lalu install sukses).
- CATATAN: frontend TIDAK punya script `dev`; scripts = start/build/test (craco). Live preview dijalankan supervisor via `yarn start` (HOST 0.0.0.0 PORT 3000). npm tidak dipakai (yarn adalah package manager proyek).
- backend & frontend RUNNING, login owner -> Dashboard Owner OK, WebSocket ONLINE/LIVE OK.
- `memory/test_credentials.md` dibuat ulang (owner/berkahayam1, admin/admin123, kasir/kasir123).

## Implemented (2026-09-03 — Edit Produksi Potong + Penyesuaian Stok Pcs)
- **Edit Produksi Potong**: endpoint baru `PUT /api/productions/{id}` (RBAC owner/admin/kasir). Stok digeser sebesar **SELISIH**, bukan reset: sumber sama -> delta_ekor = old.input_ekor - new.input_ekor; sumber diganti -> stok ekor sumber lama dikembalikan penuh & sumber baru dikurangi penuh; output pcs per produk delta = new_pcs - old_pcs via helper `_pcs_map` (bagian yang dihapus otomatis dikembalikan). allow_negative=True agar koreksi tak pernah terhalang. material_value dihitung ulang; date/operator lama dipertahankan; simpan updated_by/updated_at; activity "Produksi Potong Dikoreksi" + audit log action update; rt_emit. Helper `_validate_production` dipakai bersama POST.
- Frontend `Production.js`: tombol **Edit** per kartu (`edit-production-{id}`), ProductionDialog punya mode `initial` (prefill sumber, ekor, pcs tiap bagian), banner "Data asli", ringkasan selisih pcs, tombol "Simpan Perubahan", label "sudah dikoreksi" pada kartu yang pernah diedit.
- **Penyesuaian Stok Pcs**: `AdjustBody.delta_pcs` + diteruskan ke apply_stock & audit log. Guard: 400 bila delta_pcs pada produk tanpa satuan pcs, 400 bila semua delta 0. Frontend `Stock.js`: grid 3 kolom Kg/Ekor/Pcs (`adj-pcs`, `adj-ekor`), kolom Pcs **disabled kecuali produk terpilih bersatuan pcs** (reset ke 0 saat ganti produk) + hint. Tabel Pergerakan Stok kini menampilkan qty pcs dan kolom Stok Sesudah memakai after_pcs untuk pergerakan pcs.
- Teruji: backend testing agent 12/12 PASS (selisih stok terverifikasi: 5->8 ekor = -3 lagi, pcs 10->6 = -4, 10->15 = +5, hapus bagian = kembali penuh, ganti sumber = lama +4 / baru -6; delta_pcs +7/-3, kombinasi kg+ekor+pcs, 400 untuk non-pcs, body lama tanpa delta_pcs tetap jalan). Tanpa regresi, log bersih. UI diverifikasi manual via screenshot (dialog Edit terisi benar, kolom Pcs aktif hanya utk Ati Ampela).
- Bersih-bersih data uji (2026-09-04): 12 produksi "Test", 2 penjualan batal, 62 stock_movements, 42 activities, 42 audit_logs, 2 notifikasi dihapus (created_at >= 2026-09-04T01:2x); stok 8 produk dipulihkan dari jumlah qty movement ke nilai before_* awal (Broiler 120 ekor/225,5 kg, Kampung 40 ekor, Pejantan 80 ekor, Ceker 120 pcs, Ati Ampela 6 kg/60 pcs, Dada & Paha Atas 0). Produksi asli "Kasir Budi" (3 Sep) utuh.
- Status: owner sedang menguji manual di live preview (standby, tidak jalankan tes otomatis / fitur baru sampai ada instruksi).
