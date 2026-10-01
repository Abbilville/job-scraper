# 🔔 Job Alert Bot ke Discord (GitHub Actions + JobSpy)

Bot otomatis untuk mencari lowongan pekerjaan terbaru dari **LinkedIn** (dengan fallback **Indeed**) menggunakan library [`python-jobspy`](https://github.com/cullenwatson/JobSpy) dan mengirimkannya langsung ke channel **Discord** dalam format Discord Embed yang rapi.

Dijalankan secara otomatis dan terjadwal melalui **GitHub Actions** tanpa perlu sewa VPS/server!

---

## ✨ Fitur Utama

- 🔍 **Scraping Multi-Board**: Scraping LinkedIn dan Indeed dengan parameter pencarian yang fleksibel (posisi, lokasi, umur lowongan, dan remote).
- 🛡️ **Fallback Otomatis**: Jika LinkedIn mengalami rate-limit atau tidak menemukan hasil, bot otomatis fallback mencari ke Indeed.
- 🚫 **Anti Duplikasi**: Menggunakan `seen_jobs.json` yang dicatat dan di-commit otomatis kembali ke repository oleh GitHub Actions (`stefanzweifel/git-auto-commit-action`), sehingga alert yang sama tidak akan dikirim ulang.
- 🎨 **Discord Embed Cantik**: Dilengkapi judul lowongan yang bisa diklik, nama perusahaan, lokasi, tanggal posting, estimasi gaji (jika ada), tipe pekerjaan, dan warna brand embed yang disesuaikan.
- ⏱️ **Otomatis & Terjadwal**: Berjalan otomatis setiap 6 jam sekali via cron GitHub Actions dan mendukung trigger manual (`workflow_dispatch`).

---

## 🚀 Panduan Setup di GitHub Repository

### 1. Dapatkan Webhook URL dari Discord
1. Buka aplikasi Discord dan masuk ke server Discord Anda.
2. Buka **Server Settings** (atau klik ikon gerigi pada channel tujuan alert).
3. Pilih menu **Integrations** > **Webhooks** > **New Webhook**.
4. Beri nama bot (misal: `Job Alerts`) dan pilih channel tujuan.
5. Klik **Copy Webhook URL**.

---

### 2. Pasang Secret `DISCORD_WEBHOOK_URL` di GitHub
Agar GitHub Actions dapat mengirim pesan ke Discord tanpa membocorkan URL webhook di kode publik:

1. Buka repository GitHub Anda di browser.
2. Masuk ke tab **Settings**.
3. Di sidebar kiri, klik **Secrets and variables** > pilih **Actions**.
4. Pada tab **Secrets**, klik tombol hijau **New repository secret**.
5. Isi formulir:
   - **Name**: `DISCORD_WEBHOOK_URL`
   - **Secret**: Tempelkan (*paste*) URL Webhook Discord yang sudah disalin tadi.
6. Klik **Add secret**.

---

### 3. Aktifkan Izin Read & Write Workflow (Penting!)
Agar GitHub Actions diizinkan untuk meng-commit kembali file `seen_jobs.json`:

1. Di repository GitHub Anda, buka tab **Settings**.
2. Di sidebar kiri, pilih **Actions** > **General**.
3. Gulir ke bawah hingga bagian **Workflow permissions**.
4. Pilih opsi **Read and write permissions**.
5. Klik **Save**.

---

### 4. Menjalankan Manual (Testing via GitHub Actions)
1. Buka tab **Actions** di repository GitHub Anda.
2. Pilih workflow **Job Alert Bot** di sebelah kiri.
3. Klik tombol dropdown **Run workflow**.
4. Anda dapat langsung menjalankan dengan parameter default atau mengubah *Search Term*, *Location*, dll.
5. Klik **Run workflow** berwarna hijau untuk memulai pengujian.

---

## ⚙️ Kustomisasi Parameter Pencarian

Anda dapat mengubah parameter pencarian lowongan melalui dua cara:

### Cara A: Melalui GitHub Actions Variables
1. Buka **Settings** > **Secrets and variables** > **Actions** > tab **Variables**.
2. Tambahkan variable repository baru (opsional):
   - `SEARCH_TERM`: misal `Backend Developer` atau `Data Engineer`
   - `LOCATION`: misal `Indonesia` atau `Jakarta`
   - `HOURS_OLD`: misal `24`
   - `RESULTS_WANTED`: misal `15`
   - `SITE_NAMES`: misal `linkedin,indeed`

### Cara B: Ubah Default di `.github/workflows/job_alert.yml`
Ubah bagian `env:` pada step `Run Job Alert Script`:
```yaml
env:
  DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
  SEARCH_TERM: 'Frontend Developer'
  LOCATION: 'Indonesia'
  HOURS_OLD: '24'
  RESULTS_WANTED: '15'
```

---

## 💻 Penggunaan Lokal (Local Development)

Jika ingin menjalankan atau menguji bot di komputer lokal:

### 1. Clone & Setup Virtual Environment
```bash
# Masuk ke folder project
cd job-alerts

# Buat virtual environment
python -m venv .venv

# Aktifkan virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependensi
pip install -r requirements.txt
```

### 2. Buat File Konfigurasi `.env`
Salin template `.env.example`:
```bash
cp .env.example .env
```
Buka `.env` dan masukkan `DISCORD_WEBHOOK_URL` Anda:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
SEARCH_TERM=Frontend Developer
LOCATION=Indonesia
HOURS_OLD=24
RESULTS_WANTED=15
```

### 3. Eksekusi Script
```bash
# Menjalankan dalam mode Dry Run (hanya preview, tanpa kirim ke Discord)
python main.py --dry-run

# Menjalankan normal (mengirim ke Discord dan update seen_jobs.json)
python main.py

# Menjalankan dengan argumen khusus
python main.py --search-term "React Developer" --location "Indonesia" --results-wanted 10
```

---

## 📁 Struktur Direktori

```text
job-alerts/
├── .github/
│   └── workflows/
│       └── job_alert.yml       # Konfigurasi cron & trigger GitHub Actions
├── .env.example                # Template variabel lingkungan
├── .gitignore                  # Berkas yang diabaikan Git
├── config.py                   # Modul konfigurasi dan env loader
├── dedup.py                    # Modul deduplikasi riwayat lowongan
├── discord_notifier.py         # Formatter embed & pengirim Discord Webhook
├── main.py                     # Entry point bot
├── requirements.txt            # Dependensi Python
├── seen_jobs.json              # Database riwayat lowongan tersimpan
└── README.md                   # Dokumentasi proyek
```

---

## 📄 Lisensi
MIT License. Bebas digunakan dan dimodifikasi untuk kebutuhan pribadi maupun tim.
