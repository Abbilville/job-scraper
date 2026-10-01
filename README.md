# 🔔 Job Alert Bot ke Discord (GitHub Actions + JobSpy + AI Extraction)

Repository: [https://github.com/Abbilville/job-scraper](https://github.com/Abbilville/job-scraper)

Bot otomatis untuk mencari lowongan pekerjaan terbaru dari **LinkedIn** (dengan fallback **Indeed**) menggunakan library [`python-jobspy`](https://github.com/cullenwatson/JobSpy) dan mengirimkannya langsung ke channel **Discord** dengan **multi-channel stream routing** yang rapi dan elegan.

Didesain khusus untuk mahasiswa, fresh graduate, dan alumni **Teknologi Informasi, Ilmu Komputer, dan Sistem Informasi (UI, ITB, UGM, dsb.)** yang mengincar karir di bidang:
- **Software Engineering & DevOps**
- **Data Science, AI & Business Intelligence (BI)**
- **Product Management & Business Analysis (SI / APM)**

Dijalankan secara otomatis dan terjadwal melalui **GitHub Actions** tanpa perlu sewa VPS/server!

---

## ✨ Fitur Baru & Optimalisasi

### 1. 📢 Multi-Channel Stream Routing (Anti-Berisik)
Alih-alih menumpuk 20+ jenis lowongan dalam satu channel Discord, bot otomatis membagi alert ke channel yang sesuai dengan tema karir:

| Stream | Channel Rekomendasi | Environment Secret | Warna Embed | Cakupan Posisi |
| :--- | :--- | :--- | :--- | :--- |
| **Tech & Engineering** | `#tech-dev` | `DISCORD_WEBHOOK_TECH` | 🔵 **Biru** (`#3498DB`) | Software Engineer, Backend, Frontend, Fullstack, FDE, Mobile, DevOps |
| **Data & AI** | `#data-ai` | `DISCORD_WEBHOOK_DATA` | 🟣 **Ungu** (`#9B59B6`) | Data Scientist, Data Engineer, Data Analyst, Machine Learning, AI, BI |
| **Product & Analysis** | `#product-biz` | `DISCORD_WEBHOOK_PRODUCT` | 🟠 **Oranye** (`#E67E22`) | Product Manager, APM, Product Owner, Business Analyst, System Analyst |
| **Top Tier / Big 4** | *(Semua Stream)* | *(Otomatis)* | 🟡 **Emas** (`#F1C40F`) | Perusahaan Top Tier di stream mana pun mendapat badge & warna emas |

> **Catatan Fallback:** Jika Anda hanya mengisi `DISCORD_WEBHOOK_URL` (1 channel saja), semua lowongan otomatis dikirim ke channel tersebut.

---

### 2. 🚫 Filter Kata Kunci Negatif (`exclude_title_keywords`)
Mencegah salah tangkap lowongan non-IT untuk posisi Product & Business Analysis (seperti Sales, Medis, Dapur, atau level Senior/Lead jika fokus ke entry-level):
- **Level Tinggi yang Dieliminasi**: `Senior`, `Lead`, `Principal`, `Head of`, `Director`, `VP`.
- **Posisi Non-IT yang Dieliminasi**: `Product Marketing`, `Medical Representative`, `Sales Representative`, `Product Specialist`, `Chef`, `Cook`, `Barista`, `Nurse`, `Doctor`.

---

### 3. 🎓 Level & Seniority Filtering (`allowed_experience_levels`)
Secara default menyaring lowongan agar sesuai untuk mahasiswa, fresh graduate, dan junior:
- `internship` (Magang / Mahasiswa)
- `entry_level` (Fresh Graduate / 0-1 tahun)
- `associate` (Junior / Associate / 1-3 tahun)
- `mid_senior` (Mid-Level)

---

### 4. 🏢 Perusahaan Top Tier Tambahan
Katalog perusahaan di `config.json` mencakup:
- **Big 4 & Strategy Consulting**: PwC, Deloitte, EY, KPMG, McKinsey, BCG, Bain, Accenture.
- **Top Tech, Unicorns & Enablers**: GoTo, Traveloka, Shopee / Sea, Grab, **tiket.com**, Blibli, Bukalapak, DANA, Xendit, Kredivo, eFishery, Ajaib, Bibit / Stockbit, **DKATALIS (Bank Jago)**, **Sirclo**, **Komerce**, Ruangguru, Google, Microsoft, AWS, ByteDance, Meta.
- **Top Tier Banking & FinTech**: BCA, Bank Mandiri, BRI, BNI, Bank Indonesia (BI), DBS, CIMB Niaga, OCBC, BTPN / Jenius.
- **Conglomerates, Healthcare & FMCG**: Telkom/Telkomsel, Astra International, Unilever, Nestlé, P&G, Danone, Paragon (Wardah), Indofood, **Mayora**, **Wings Group**, **Kalbe Farma**, Pertamina.

---

### 5. 🛠️ Smart Tech Stack & SI Skills Extraction
Mendeteksi keterampilan khusus dari deskripsi loker:
- **Product & SI**: `Jira`, `Confluence`, `Figma`, `Wireframing`, `PRD`, `User Stories`, `BPMN`, `UML`, `BRD`, `FSD`, `A/B Testing`, `Mixpanel`, `Product Roadmap`, `Agile/Scrum`.
- **BI & Data**: `Power BI`, `Tableau`, `Looker`, `Metabase`, `DAX`, `Excel`, `SQL`, `Data Warehouse`, `ETL`, `dbt`, `Snowflake`, `BigQuery`.
- **Engineering & AI**: `Python`, `TypeScript`, `React`, `Next.js`, `FastAPI`, `Docker`, `Kubernetes`, `AWS`, `PyTorch`, `LLM`, `RAG`, dsb.

---

## 🚀 Panduan Setup GitHub Repository

### 1. Pasang Webhook Discord
Buat webhook di Discord (bisa 1 channel umum atau 3 channel terpisah sesuai stream):
- **Opsi A (Satu Channel untuk Semua)**: Buat 1 webhook lalu simpan sebagai `DISCORD_WEBHOOK_URL`.
- **Opsi B (Rekomendasi - Multi-Channel)**:
  1. Channel `#tech-dev` -> Webhook URL -> Simpan sebagai secret `DISCORD_WEBHOOK_TECH`
  2. Channel `#data-ai` -> Webhook URL -> Simpan sebagai secret `DISCORD_WEBHOOK_DATA`
  3. Channel `#product-biz` -> Webhook URL -> Simpan sebagai secret `DISCORD_WEBHOOK_PRODUCT`

### 2. Pasang Secret di GitHub
1. Buka repo: [https://github.com/Abbilville/job-scraper](https://github.com/Abbilville/job-scraper)
2. Masuk ke **Settings** > **Secrets and variables** > **Actions**.
3. Klik **New repository secret**:
   - `DISCORD_WEBHOOK_URL` *(Fallback default)*
   - `DISCORD_WEBHOOK_TECH` *(Opsional)*
   - `DISCORD_WEBHOOK_DATA` *(Opsional)*
   - `DISCORD_WEBHOOK_PRODUCT` *(Opsional)*
   - `AI_API_URL` *(Opsional - jika deploy AI ke VPS)*
   - `AI_API_KEY` *(Opsional)*

### 3. Izin Read & Write Workflow (Sekali Saja)
1. Buka tab **Settings** > **Actions** > **General**.
2. Gulir ke bawah ke bagian **Workflow permissions**.
3. Pilih **Read and write permissions** lalu klik **Save**.

### 4. Jalankan Workflow
1. Buka tab **Actions** di GitHub.
2. Pilih workflow **Job Alert Bot** > klik **Run workflow**.

---

## 💻 Menjalankan Secara Lokal (Local Development)

```bash
# Clone & masuk folder
git clone https://github.com/Abbilville/job-scraper.git
cd job-scraper

# Setup venv
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/Mac

# Install dependensi
pip install -r requirements.txt

# Menjalankan unit tests
python -m unittest test_smoke.py

# Menjalankan Dry Run (preview di terminal tanpa mengirim ke Discord)
python main.py --dry-run
```

---

## 📁 Struktur Direktori Proyek

```text
job-scraper/
├── .github/
│   └── workflows/
│       └── job_alert.yml       # Workflow GitHub Actions (cron & dispatch)
├── .env.example                # Template konfigurasi environment variables
├── .gitignore                  # Berkas yang diabaikan Git (.venv, __pycache__, .env)
├── config.json                 # PUSAT KONTROL (search terms, exclude keywords, streams, companies)
├── config.py                   # Loader konfigurasi & resolver multi-webhook
├── company_filter.py           # Classifier Top Companies (Big 4, Tech, Bank, FMCG)
├── extractor.py                # Regex + AI extractor (Skills, YoE, Level)
├── dedup.py                    # Deduplikasi riwayat alert (seen_jobs.json)
├── discord_notifier.py         # Multi-stream router & embed builder
├── main.py                     # Pipeline utama orchestrator bot
├── requirements.txt            # Dependensi Python
├── seen_jobs.json              # Basis data riwayat alert terkirim
├── test_smoke.py               # Unit test suite
└── README.md                   # Dokumentasi proyek
```

---

## 📄 Lisensi
MIT License. Bebas digunakan dan dikembangkan untuk komunitas kampus maupun pribadi.
