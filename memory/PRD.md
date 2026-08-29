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
