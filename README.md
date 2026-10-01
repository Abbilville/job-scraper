# 🔔 Job Alert Bot ke Discord (GitHub Actions + JobSpy + AI Extraction)

Repository: [https://github.com/Abbilville/job-scraper](https://github.com/Abbilville/job-scraper)

Bot otomatis untuk mencari lowongan pekerjaan terbaru dari **LinkedIn** (dengan fallback **Indeed**) menggunakan library [`python-jobspy`](https://github.com/cullenwatson/JobSpy) dan mengirimkannya langsung ke channel **Discord** dalam format Discord Embed yang rapi, informatif, dan mewah.

Didesain khusus untuk mahasiswa, fresh graduate, dan alumni (seperti anak-anak UI, ITB, UGM, dsb.) dengan fitur kurasi **Perusahaan Top Tier (Big 4, Top Tech Unicorns, Banking, & FMCG)** serta **Ekstraksi Keterampilan (Skills), Pengalaman (YoE), dan Level Jabatan** berbasis Regex + AI!

Dijalankan secara otomatis dan terjadwal melalui **GitHub Actions** tanpa perlu sewa VPS/server!

---

## ✨ Fitur Utama

- ⚙️ **Konfigurasi Terpusat di `config.json`**:
  - Semua pengaturan kata kunci, lokasi, situs loker, filter mode, dan katalog perusahaan top tier diatur dalam satu file `config.json`. Anda tidak perlu mengubah kode program.
- 🚀 **Role Kekinian untuk Mahasiswa & Lulusan CompSci**:
  - Termasuk posisi yang sedang happening: **Forward Deployed Engineer (FDE)**, **AI Engineer**, **Machine Learning Engineer**, **Data Scientist**, **Data Engineer**, **DevOps / Cloud Engineer**, **Fullstack**, **Backend**, **Frontend**, dan **Mobile Developer**.
- 🧠 **Smart Extraction (Skills, YoE, Level)**:
  - **Keahlian (Tech Stack)**: Otomatis mendeteksi bahasa pemrograman, framework, dan tools (React, Next.js, Node.js, FastAPI, PyTorch, Docker, Kubernetes, AWS, SQL, dsb.).
  - **Pengalaman (YoE)**: Otomatis mengekstrak tahun pengalaman yang dibutuhkan (cth: `2-4 tahun`, `Min. 1 tahun`, `Fresh Graduate (0-1 tahun)`, `Internship`).
  - **Level Jabatan**: Mengklasifikasikan lowongan menjadi `Junior / Associate`, `Internship`, `Mid-Level`, atau `Senior / Lead`.
- 🤖 **Integrasi AI Microservice (Opsional / Siap Deploy ke VPS)**:
  - Jika `AI_API_URL` dan `AI_API_KEY` diisi di environment variable / secret, bot akan memanggil endpoint AI VPS Anda untuk ekstraksi dan ringkasan mendalam.
  - Jika kosong, bot otomatis fallback ke **Rule-Based Regex Extractor** lokal tanpa error.
- 🏆 **Kurasi & Deteksi Perusahaan Top Tier**:
  - **Big 4 & Strategy Consulting**: PwC, Deloitte, EY, KPMG, McKinsey, BCG, Bain, Accenture.
  - **Top Tech Giants & Unicorns**: GoTo (Gojek & Tokopedia), Traveloka, Shopee / Sea, Grab, Blibli, Bukalapak, DANA, Xendit, Kredivo, eFishery, Ruangguru, Google, Microsoft, AWS, ByteDance / TikTok, Meta.
  - **Top Tier Banking & FinTech**: BCA, Bank Mandiri, BRI, BNI, Bank Indonesia (BI), DBS Bank, CIMB Niaga, OCBC, Bibit, Ajaib.
  - **Top Conglomerates, Telco & FMCG**: Telkomsel, Astra International, Unilever, Nestlé, P&G, Danone, Indofood, Paragon (Wardah), Pertamina.
- 🎯 **3 Mode Filter Perusahaan (`filter_mode`)**:
  - `highlight` *(Default)*: Mengirim semua lowongan, namun loker dari Top Tier otomatis diberi **Badge Emas Khusus** dan diposisikan di urutan paling atas.
  - `only_top`: Eksklusif **HANYA** mengirim lowongan jika perusahaannya berasal dari daftar Top Tier.
  - `all`: Kirim semua lowongan apa adanya.
- 🚫 **Anti Duplikasi**: Menyimpan riwayat lowongan di `seen_jobs.json` yang di-commit otomatis kembali ke repository oleh GitHub Actions.

---

## 🛠️ Format Payload AI (Jika Deploy ke VPS)

Jika Anda mendeploy microservice AI (misal FastAPI + LLM seperti Ollama / OpenAI / vLLM) ke VPS:

**Request POST ke `AI_API_URL`**:
```json
{
  "title": "Junior Frontend Engineer",
  "company": "PwC Indonesia",
  "description": "Full job description text..."
}
```

**Expected JSON Response dari AI VPS**:
```json
{
  "skills": ["React", "TypeScript", "Tailwind CSS", "Docker"],
  "yoe": "1-2 tahun",
  "seniority": "Junior / Associate",
  "summary": "Membangun sistem antarmuka web modern dengan React dan TypeScript."
}
```

*Catatan: Jika service VPS Anda down atau tidak disetel, bot tetap berjalan normal menggunakan rule-based extractor bawaan.*

---

## 🚀 Panduan Setup di GitHub Repository

### 1. Dapatkan Webhook URL dari Discord
1. Buka aplikasi Discord dan masuk ke server Discord Anda.
2. Buka **Server Settings** (atau klik ikon gerigi pada channel tujuan alert).
3. Pilih menu **Integrations** > **Webhooks** > **New Webhook**.
4. Beri nama bot (misal: `Job Alerts`) dan pilih channel tujuan.
5. Klik **Copy Webhook URL**.

---

### 2. Pasang Secret di GitHub Repository
1. Buka repository GitHub: `https://github.com/Abbilville/job-scraper`
2. Masuk ke tab **Settings** > **Secrets and variables** > **Actions**.
3. Klik tombol hijau **New repository secret**.
4. Tambahkan secret berikut:
   - `DISCORD_WEBHOOK_URL` *(Wajib)*: Masukkan URL Webhook Discord Anda.
   - `AI_API_URL` *(Opsional)*: URL endpoint AI di VPS Anda (cth: `https://ai.domainanda.com/extract`).
   - `AI_API_KEY` *(Opsional)*: Bearer token autentikasi jika endpoint AI dilindungi.

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
4. Anda dapat langsung klik tombol hijau **Run workflow** untuk menjalankan dengan pengaturan `config.json`.

---

## 💻 Penggunaan Lokal (Local Development)

### 1. Setup Virtual Environment
```bash
# Clone repository
git clone https://github.com/Abbilville/job-scraper.git
cd job-scraper

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

### 2. Atur Environment Variable
Salin template `.env.example`:
```bash
cp .env.example .env
```
Buka `.env` dan masukkan `DISCORD_WEBHOOK_URL` Anda.

### 3. Eksekusi Script
```bash
# Menjalankan dalam mode Dry Run (hanya preview di terminal, tanpa kirim ke Discord)
python main.py --dry-run

# Menjalankan hanya untuk lowongan Top Tier (Big 4 / Top Tech)
python main.py --dry-run --filter-mode only_top

# Menjalankan normal (mengirim ke Discord dan update seen_jobs.json)
python main.py
```

---

## 📁 Struktur Direktori

```text
job-scraper/
├── .github/
│   └── workflows/
│       └── job_alert.yml       # Konfigurasi cron & manual trigger GitHub Actions
├── .env.example                # Template variabel lingkungan
├── .gitignore                  # Berkas yang diabaikan Git
├── config.json                 # PUSAT PENGATURAN (search terms, lokasi, sites, top companies)
├── config.py                   # Loader config.json & env override
├── company_filter.py           # Classifier Top Companies (Big 4, Tech, Bank, FMCG)
├── extractor.py                # Ekstraktor Skills, YoE, Seniority (Regex + AI HTTP Client)
├── dedup.py                    # Deduplikasi riwayat loker (seen_jobs.json)
├── discord_notifier.py         # Formatter Discord Embed & Webhook sender
├── main.py                     # Entry point bot
├── requirements.txt            # Dependensi Python
├── seen_jobs.json              # Database riwayat lowongan tersimpan
├── test_smoke.py               # Test suite unit & smoke test
└── README.md                   # Dokumentasi proyek
```

---

## 📄 Lisensi
MIT License. Bebas digunakan dan dimodifikasi untuk kebutuhan komunitas atau pribadi.
