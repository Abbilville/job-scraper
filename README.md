# 🔔 Job Alert Bot ke Discord (GitHub Actions + JobSpy)

Bot otomatis untuk mencari lowongan pekerjaan terbaru dari **LinkedIn** (dengan fallback **Indeed**) menggunakan library [`python-jobspy`](https://github.com/cullenwatson/JobSpy) dan mengirimkannya langsung ke channel **Discord** dalam format Discord Embed yang rapi dan informatif.

Didesain khusus untuk pencari kerja dan mahasiswa/alumni (seperti anak-anak UI, ITB, fresh grads, dsb.) dengan fitur kurasi **Perusahaan Top Tier (Big 4, Top Tech Unicorns, Banking, & FMCG)**!

Dijalankan secara otomatis dan terjadwal melalui **GitHub Actions** tanpa perlu sewa VPS/server!

---

## ✨ Fitur Utama

- 🔍 **Multi-Search & Multi-Location**:
  - Mendukung banyak kata kunci sekaligus (misal: `Frontend Developer, Software Engineer, Web Developer`).
  - Mendukung banyak lokasi sekaligus (misal: `Indonesia, Jakarta, Remote`).
- 🏆 **Kurasi & Deteksi Perusahaan Top Tier**:
  - **Big 4 & Strategy Consulting**: PwC, Deloitte, EY, KPMG, McKinsey, BCG, Bain, Accenture.
  - **Top Tech Giants & Unicorns**: GoTo (Gojek & Tokopedia), Traveloka, Shopee / Sea, Grab, Blibli, Bukalapak, DANA, Xendit, Kredivo, eFishery, Ruangguru, Google, Microsoft, AWS, ByteDance, Meta.
  - **Top Banking & FinTech**: Bank Central Asia (BCA), Bank Mandiri, BRI, BNI, Bank Indonesia, DBS, CIMB Niaga, OCBC, Bibit, Ajaib.
  - **Top Conglomerates, Telco & FMCG**: Telkom / Telkomsel, Astra International, Unilever, Nestlé, P&G, Danone, Indofood, Paragon (Wardah), Pertamina.
- 🎯 **3 Mode Filter Perusahaan (`FILTER_MODE`)**:
  - `highlight` *(Default - Sangat Direkomendasikan)*: Mengirim semua lowongan yang cocok, namun loker dari perusahaan Top Tier / Big 4 / Tech Giants otomatis diberi **badge emas khusus** dan diprioritaskan di urutan teratas.
  - `only_top`: Eksklusif **HANYA** mengirim lowongan jika perusahaannya berasal dari daftar Top Tier.
  - `all`: Mengirim semua lowongan tanpa klasifikasi khusus.
- 🛡️ **Fallback Otomatis**: Jika LinkedIn mengalami rate-limit atau tidak menemukan hasil, bot otomatis fallback mencari ke Indeed.
- 🚫 **Anti Duplikasi**: Menggunakan `seen_jobs.json` yang dicatat dan di-commit otomatis kembali ke repository oleh GitHub Actions (`stefanzweifel/git-auto-commit-action`), sehingga alert yang sama tidak akan dikirim ulang.
- 🎨 **Discord Embed Cantik**: Dilengkapi judul lowongan yang bisa diklik, nama perusahaan, tag perusahaan unggulan, lokasi, tanggal posting, estimasi gaji (jika ada), tipe pekerjaan, dan warna brand embed yang disesuaikan.
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
4. Anda dapat mengatur:
   - **Kata Kunci / Posisi**: Pisahkan dengan koma (cth: `Frontend Developer, Software Engineer`).
   - **Lokasi**: Pisahkan dengan koma (cth: `Indonesia, Jakarta, Remote`).
   - **Mode Filter Perusahaan**: Pilih `highlight`, `only_top`, atau `all`.
   - **Hours Old** & **Results Wanted**.
5. Klik tombol hijau **Run workflow** untuk memulai pencarian.

---

## ⚙️ Kustomisasi Parameter Pencarian

Anda dapat mengubah konfigurasi default tanpa mengubah kode program melalui dua cara:

### Cara A: Melalui GitHub Actions Variables
1. Buka **Settings** > **Secrets and variables** > **Actions** > tab **Variables**.
2. Tambahkan variable repository baru (opsional):
   - `SEARCH_TERMS`: `Frontend Developer, Software Engineer, Fullstack Developer`
   - `LOCATIONS`: `Indonesia, Jakarta, Remote`
   - `FILTER_MODE`: `highlight` (atau `only_top` untuk loker top tier saja)
   - `HOURS_OLD`: `24`
   - `RESULTS_WANTED`: `15`
   - `SITE_NAMES`: `linkedin,indeed`
   - `CUSTOM_TOP_COMPANIES`: `Nama Perusahaan Impian 1, Startup X`

### Cara B: Ubah Default di `.github/workflows/job_alert.yml`
Ubah bagian `env:` pada step `Run Job Alert Script`:
```yaml
env:
  DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
  SEARCH_TERMS: 'Frontend Developer, Software Engineer'
  LOCATIONS: 'Indonesia, Jakarta, Remote'
  FILTER_MODE: 'highlight' # atau 'only_top'
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
Buka `.env` dan sesuaikan parameter:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
SEARCH_TERMS=Frontend Developer, Software Engineer
LOCATIONS=Indonesia, Jakarta, Remote
FILTER_MODE=highlight
HOURS_OLD=24
RESULTS_WANTED=15
```

### 3. Eksekusi Script
```bash
# Menjalankan dalam mode Dry Run (hanya preview di terminal, tanpa kirim ke Discord)
python main.py --dry-run

# Menjalankan hanya untuk perusahaan Top Tier (Big 4 / Top Tech)
python main.py --dry-run --filter-mode only_top

# Menjalankan normal (mengirim ke Discord dan update seen_jobs.json)
python main.py

# Menjalankan dengan argumen khusus
python main.py --search-terms "Frontend Developer, UI Designer" --locations "Indonesia, Remote" --results-wanted 10
```

---

## 📁 Struktur Direktori

```text
job-alerts/
├── .github/
│   └── workflows/
│       └── job_alert.yml       # Konfigurasi cron & manual trigger GitHub Actions
├── .env.example                # Template variabel lingkungan
├── .gitignore                  # Berkas yang diabaikan Git
├── company_filter.py           # Database & classifier Big 4, Top Tech, Bank, FMCG
├── config.py                   # Modul konfigurasi dan env loader
├── dedup.py                    # Modul deduplikasi riwayat lowongan
├── discord_notifier.py         # Formatter embed & pengirim Discord Webhook
├── main.py                     # Entry point orchestrator bot
├── requirements.txt            # Dependensi Python
├── seen_jobs.json              # Database riwayat lowongan tersimpan
├── test_smoke.py               # Unit & smoke test
└── README.md                   # Dokumentasi proyek
```

---

## 📄 Lisensi
MIT License. Bebas digunakan dan dimodifikasi untuk kebutuhan komunitas atau pribadi.
