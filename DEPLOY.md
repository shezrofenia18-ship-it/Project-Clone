# Panduan Deploy — Berkah Ayam Mili

Sistem POS & manajemen bisnis ayam potong.
Stack: **React** (frontend) · **FastAPI** (backend) · **MongoDB** (database).

---

## ⚠️ BACA INI DULU: Vercel tidak bisa menampung backend

Vercel **sangat bagus untuk frontend**, tapi **tidak bisa dipakai untuk backend** aplikasi ini.

Alasannya, backend Berkah Ayam Mili punya 3 hal yang butuh server hidup terus-menerus:

| Fitur | Kenapa mati di Vercel |
|---|---|
| **Tutup buku otomatis jam 21:00 WIB** | Penjadwal butuh proses yang hidup 24 jam. Vercel mematikan proses setelah tiap permintaan selesai, jadi jam 21:00 tidak akan ada yang menjalankannya. |
| **Sinkronisasi realtime (WebSocket)** | Stok & harga berubah seketika antar-perangkat lewat koneksi WebSocket yang terus terbuka. Vercel tidak mendukung koneksi terus-menerus. |
| **Upload foto** | Vercel tidak punya penyimpanan permanen; file yang diunggah akan hilang. |

**Kesimpulan:** frontend di Vercel silakan, tapi backend harus di tempat lain.

### Susunan yang disarankan

```
┌──────────────────────┐
│  Frontend (React)    │  ->  Vercel            (gratis)
└──────────┬───────────┘
           │ REACT_APP_BACKEND_URL
┌──────────▼───────────┐
│  Backend (FastAPI)   │  ->  Railway / Render   (~$5-10/bln)
└──────────┬───────────┘
           │ MONGO_URL
┌──────────▼───────────┐
│  Database (MongoDB)  │  ->  MongoDB Atlas      (gratis 512 MB)
└──────────────────────┘
┌──────────────────────┐
│  Foto produk & bukti │  ->  Cloudflare R2      (gratis 10 GB)
└──────────────────────┘
```

Kebutuhan aplikasi ini kecil: **254 dokumen** (75 penjualan, 14 produk, 5 pengguna).
Tier gratis MongoDB Atlas & Cloudflare R2 lebih dari cukup untuk bertahun-tahun.

---

## Langkah 1 — Siapkan database (MongoDB Atlas)

1. Daftar di [mongodb.com/atlas](https://www.mongodb.com/atlas) → buat cluster **M0 (gratis)**.
2. Menu **Database Access** → buat user + password. **Catat passwordnya.**
3. Menu **Network Access** → tambah IP `0.0.0.0/0` (izinkan dari mana saja), karena IP Railway/Render berubah-ubah.
4. Tombol **Connect** → **Drivers** → salin connection string:
   ```
   mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

> ⚠️ Kalau password mengandung `@ : / ? # [ ] %`, karakter itu **wajib di-encode**
> (contoh: `@` jadi `%40`). Kalau tidak, koneksi akan gagal.

### Pindahkan data lama Anda

Backup sudah tersedia di project ini: **`/app/backup/berkah-ayam-mili-backup.gz`**
(26 KB, 254 dokumen, sudah diverifikasi bisa dipulihkan).

Unduh file itu lewat editor Emergent (**bukan** lewat GitHub — file ini diblokir
`.gitignore` karena berisi data keuangan & hash password). Lalu jalankan di komputer Anda:

```bash
mongorestore \
  --uri="mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net" \
  --archive=berkah-ayam-mili-backup.gz \
  --gzip \
  --nsFrom='test_database.*' \
  --nsTo='berkah_ayam_mili.*'
```

Bagian `--nsFrom/--nsTo` sekaligus mengganti nama database dari `test_database`
(nama bawaan template) menjadi `berkah_ayam_mili`.

Untuk membuat backup baru kapan pun:
```bash
mongodump --uri="$MONGO_URL" --db=test_database \
  --archive=backup-$(date +%F).gz --gzip
```

---

## Langkah 2 — Deploy backend (Railway atau Render)

1. Hubungkan repo GitHub Anda, set **Root Directory** = `backend`
2. **Start command:**
   ```
   uvicorn server:app --host 0.0.0.0 --port $PORT
   ```
   > Wajib pakai `$PORT` dari hosting, jangan menulis angka 8001.
3. Isi environment variables — daftar lengkapnya ada di **`backend/.env.example`**.
   Yang wajib diperhatikan:

   | Variabel | Tindakan |
   |---|---|
   | `MONGO_URL` | Connection string Atlas dari Langkah 1 |
   | `DB_NAME` | `berkah_ayam_mili` |
   | `JWT_SECRET` | **Buat baru**: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `CORS_ORIGINS` | Domain Vercel Anda, mis. `https://berkah-ayam-mili.vercel.app` |
   | `ADMIN_*` | Salin dari `.env` lama |
   | `META_*` / `WA_*` | Salin dari `.env` lama (tetap jalan di hosting mana pun) |
   | `DISABLE_SEED` | *(opsional, pengaman ganda)* isi `true` untuk memastikan auto-seed data demo mati |

   > 🔒 **Auto-seed data demo DIBLOKIR otomatis di production** (`backend/env_guard.py`).
   > Railway/Render menyuntikkan `RAILWAY_ENVIRONMENT` / `RENDER` sendiri, dan itu sudah
   > cukup untuk mematikan seed: produk/pelanggan/penjualan contoh tidak dibuat, produk
   > potongan yang sudah dihapus tidak hidup lagi, akun demo (admin/kasir/operator/owner2)
   > tidak dibuat ulang, dan **password owner tidak pernah di-reset**. Satu-satunya penulisan
   > akun di production: membuat owner utama dari `ADMIN_USERNAME`/`ADMIN_PASSWORD` **hanya
   > bila akun itu belum ada** (deploy pertama). Untuk hosting lain yang tidak menyuntikkan
   > variabel tersebut, set `APP_ENV=production` atau `DISABLE_SEED=true`.

4. Setelah live, catat alamat backend-nya (mis. `https://xxx.up.railway.app`).
   Uji cepat: buka `https://xxx.up.railway.app/api/products` — harus meminta login (401), **bukan** error 500.

---

## Langkah 3 — Deploy frontend (Vercel)

1. Import repo GitHub → set **Root Directory** = `frontend`
2. Build settings sudah otomatis terbaca dari **`frontend/vercel.json`**
   (termasuk aturan *rewrite* agar React Router tidak error 404 saat halaman di-refresh).
3. Tambahkan 1 environment variable:
   ```
   REACT_APP_BACKEND_URL = https://xxx.up.railway.app
   ```
   > Tanpa garis miring di akhir, dan **tanpa** `/api`.

> ⚠️ Variabel `REACT_APP_*` **tertanam permanen saat build**. Kalau nanti diubah,
> Anda **wajib Redeploy** di Vercel — mengubah nilainya saja tidak berpengaruh.

4. Setelah frontend live, **kembali ke backend** dan pastikan `CORS_ORIGINS`
   sudah berisi domain Vercel tersebut, lalu restart backend.

---

## Langkah 4 — Nyalakan penyimpanan foto (cukup isi env, TANPA ubah kode)

Penyimpanan foto sudah dibuat **portabel**. Backend memilih penyedia sendiri
saat start, jadi Anda **tidak perlu menyentuh kode** sama sekali.

Urutan pemilihan otomatis (`STORAGE_BACKEND="auto"`, bawaan):

| Kondisi env | Penyedia terpilih |
|---|---|
| `S3_BUCKET` + `S3_ACCESS_KEY_ID` + `S3_SECRET_ACCESS_KEY` terisi | **s3** (Cloudflare R2 / AWS S3) |
| hanya `EMERGENT_LLM_KEY` terisi | **emergent** (khusus di dalam Emergent) |
| tidak ada keduanya | **local** (disk server) |

Bisa juga dipaksa manual: `STORAGE_BACKEND=s3` / `emergent` / `local`.

### Menyalakan Cloudflare R2

1. Dashboard Cloudflare → **R2** → **Create bucket** (mis. `berkah-ayam-mili`)
2. **Manage R2 API Tokens** → buat token dengan izin **Object Read & Write**
3. Isi 4 variabel ini di hosting backend Anda:
   ```
   S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   S3_BUCKET=berkah-ayam-mili
   S3_ACCESS_KEY_ID=<dari langkah 2>
   S3_SECRET_ACCESS_KEY=<dari langkah 2>
   ```
4. Restart backend. Selesai.

> `S3_REGION` tidak perlu diisi — kode mendeteksi endpoint R2 dan otomatis
> memakai `auto` (R2 mewajibkan nilai itu).

### Cara memastikan penyedia mana yang aktif

Saat start, backend mencetak barisnya di log:

```
INFO:berkah:Penyimpanan berkas siap -> s3 (bucket=berkah-ayam-mili, endpoint=https://xxx.r2.cloudflarestorage.com, region=auto)
```

Kalau kredensial salah, backend **tetap hidup** (kasir masih bisa jualan) tapi
log akan menulis `Penyimpanan berkas GAGAL disiapkan` — itu petunjuk paling cepat.

> ⚠️ Jangan pakai `local` untuk toko sungguhan di Railway/Render. Disk di sana
> bersifat sementara: semua foto **hilang** setiap kali aplikasi redeploy.

> **Catatan:** `EMERGENT_LLM_KEY` **bukan** kunci AI. Aplikasi ini tidak punya
> fitur AI sama sekali (nol library AI diimpor) — kunci itu semata-mata tiket
> masuk ke object storage Emergent. Anda **tidak perlu** membeli API key
> OpenAI/Anthropic/Google.

### Memindahkan foto lama

Foto yang sudah ada tersimpan di storage Emergent dan tidak ikut pindah otomatis.
Jumlahnya biasanya sedikit (foto produk & bukti pengeluaran). Cara termudah:
unggah ulang lewat menu **Produk & Harga** setelah R2 aktif.

---

## Berkas pendukung deploy yang sudah disiapkan

| Berkas | Fungsi |
|---|---|
| `backend/.env.example` | Template semua env backend, bertanda [GANTI]/[SALIN]/[BARU] |
| `frontend/.env.example` | Template env frontend |
| `backend/Procfile` | Perintah start untuk Railway/Render/Heroku (memakai `$PORT`) |
| `backend/runtime.txt` | Menetapkan Python 3.11 |
| `backend/storage.py` | Lapisan penyimpanan portabel (s3/emergent/local) |
| `frontend/vercel.json` | Build config + rewrite SPA untuk Vercel |
| `frontend/yarn.lock` | Mengunci versi paket agar build di hosting sama persis |

> **Penting soal `--workers`:** `Procfile` sengaja memakai `--workers 1`.
> Aplikasi ini punya penjadwal tutup buku dan manajer WebSocket yang menyimpan
> state di memori proses. Kalau workernya lebih dari satu, **rekap tutup buku
> bisa terkirim berkali-kali** dan siaran realtime hanya sampai ke sebagian
> perangkat.

---

## Daftar periksa sebelum dianggap selesai

- [ ] Data lama sudah masuk Atlas (cek: jumlah penjualan = 75)
- [ ] `JWT_SECRET` sudah diganti yang baru
- [ ] `CORS_ORIGINS` sudah berisi domain Vercel (bukan `*`)
- [ ] `DB_NAME` bukan lagi `test_database`
- [ ] Bisa login sebagai `owner`
- [ ] Transaksi POS berhasil sampai struk muncul
- [ ] Unduh PDF laporan berhasil (penjualan, laba rugi, stok)
- [ ] Sinkronisasi realtime jalan (buka 2 tab, ubah stok di satu tab)
- [ ] Upload foto produk berhasil (lihat log: penyedia yang aktif = `s3`)
- [ ] Rekap WhatsApp terkirim

---

## Masalah yang sering terjadi

| Gejala | Penyebab & solusi |
|---|---|
| Semua permintaan API gagal, console browser bilang **CORS** | `CORS_ORIGINS` di backend belum memuat domain frontend. Tambahkan lalu restart backend. |
| Halaman putih, atau **404 saat halaman di-refresh** | Aturan rewrite SPA tidak terbaca. Pastikan `frontend/vercel.json` ada dan Root Directory = `frontend`. |
| Frontend masih menembak server lama | `REACT_APP_BACKEND_URL` diubah tapi belum **Redeploy** di Vercel. |
| Backend gagal start, log menyebut **`ModuleNotFoundError`** | Dependensi belum lengkap. Pastikan `pip install -r requirements.txt` jalan dan Root Directory = `backend`. |
| Login selalu gagal walau password benar | `JWT_SECRET` berubah setelah token lama dibuat. Hapus data situs di browser lalu login ulang. |
| Tidak bisa konek MongoDB Atlas | IP belum di-whitelist (`0.0.0.0/0`), atau password belum di-URL-encode. |
| **Tutup buku otomatis tidak jalan** | Backend di-deploy ke layanan *serverless* (Vercel/Netlify). Pindahkan ke Railway/Render. |
| **Rekap WhatsApp terkirim berkali-kali** | Backend jalan dengan lebih dari 1 worker. Pastikan `--workers 1` seperti di `Procfile`. |
| Upload foto error | Cek log startup: penyedia yang aktif apa? Kalau `emergent` padahal di luar Emergent, berarti env `S3_*` belum terisi. |
| Foto hilang setelah redeploy | Penyedia yang aktif `local`. Isi env `S3_*` supaya berpindah ke R2/S3. |
