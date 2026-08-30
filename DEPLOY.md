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

## Langkah 4 — Ganti penyimpanan foto (WAJIB)

Saat ini upload foto memakai **Object Storage milik Emergent**, yang hanya hidup
di dalam Emergent. Di luar Emergent, `POST /api/upload` akan gagal.

Yang terpengaruh:
- Foto produk (folder `products`)
- Foto bukti pengeluaran (folder `proofs`)

Kode yang perlu diubah: fungsi `init_storage()`, `put_object()`, dan `get_object()`
di `backend/server.py` (sekitar baris 48–90).

> **Catatan:** `EMERGENT_LLM_KEY` di file env **bukan** kunci AI.
> Aplikasi ini tidak punya fitur AI sama sekali (nol library AI diimpor) —
> kunci itu semata-mata dipakai untuk masuk ke object storage Emergent.
> Jadi Anda **tidak perlu** membeli API key OpenAI/Anthropic/Google.

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
- [ ] Upload foto produk berhasil (setelah Langkah 4)
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
| Upload foto error | Langkah 4 belum dikerjakan. |
