# RAG Putusan Narkotika PN Rantau Prapat

Asisten tanya-jawab berbasis *Retrieval-Augmented Generation* (RAG) di atas 51 putusan pidana narkotika Pengadilan Negeri Rantau Prapat tahun 2023. Pertanyaan tentang satu perkara dijawab dari potongan putusan beserta sitasinya; pertanyaan statistik dijawab lewat query SQL ke tabel metadata supaya angkanya pasti benar.

Project ini adalah pengembangan dari [Dataset-Narkotika_092_074](https://github.com/rohid001/Dataset-Narkotika_092_074).

## Arsitektur

```text
51 PDF ─► extract.py ─► teks bersih ─┬─► metadata.py ─► metadata.db (SQLite) ──────────┐
                                     └─► chunking.py ─► chunks.jsonl ─► index.py      │
                                                                         │            │
                                                          Chroma (vektor) + BM25      │
                                                                         │            │
pertanyaan ─► router.py ──► "agregat" ─► LLM menulis SQL ─► SQLite ──────┼────────────┘
                       └──► "rag" ─────► retrieve.py (hibrida + filter nomor perkara)
                                          └─► rag.py: konteks + fakta tabel ─► LLM ─► jawaban + sitasi
```

## Dataset

| Atribut | Nilai |
| --- | --- |
| Sumber | Direktori Putusan Mahkamah Agung RI |
| Pengadilan | PN Rantau Prapat, tingkat pertama |
| Jumlah putusan | 51 perkara `Pid.Sus` tahun 2023, diputus Juni–Oktober 2023 |
| Ukuran | 1.333 halaman PDF; 29% teks mentahnya noise (header, disclaimer, nomor halaman) |
| Narkotika | Sabu di 49 perkara, ekstasi di 235, sabu + ganja di 310 |
| Pasal terbanyak | 112 ayat (1): 25 perkara; 114 ayat (1): 16 perkara |
| Vonis | 1–12 tahun, median 5 tahun 6 bulan; vonis lebih ringan dari tuntutan di 50 dari 51 perkara |

### Batasan

- Hanya satu pengadilan dan satu tahun, jadi hasilnya tidak bisa digeneralisasi.
- Hanya putusan tingkat pertama; tidak ada banding atau kasasi.
- Nama saksi dan alamat disamarkan secara otomatis (regex), jadi bisa ada yang terlewat. Nama terdakwa dipertahankan karena putusan bersifat publik dan dibutuhkan untuk pertanyaan lintas perkara.

## Stack

| Lapisan | Pilihan |
| --- | --- |
| Bahasa | Python 3.12 (venv) |
| Ekstraksi PDF | PyMuPDF |
| Data | pandas, SQLite |
| Embedding | `BAAI/bge-m3` (lokal), `intfloat/multilingual-e5-small` (lokal, ringan), `gemini-embedding-001` (API, untuk deploy) |
| Retrieval | Chroma (vektor) + rank-bm25, digabung dengan Reciprocal Rank Fusion |
| LLM | Gemini API (`gemini-3.5-flash`), cadangan Groq (`openai/gpt-oss-20b`) |
| Antarmuka dan hosting | Streamlit, Streamlit Community Cloud |

## Menjalankan

Perintah di bawah untuk terminal PowerShell (VS Code) di Windows dengan Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
copy .env.example .env             # lalu isi API key di .env

python -m src.build_manifest       # Fase 0: peta file PDF -> nomor perkara
python -m src.extract              # Fase 1: teks bersih per perkara
python -m src.metadata             # Fase 2: tabel metadata (SQLite + CSV)
python -m src.metadata --sampel 10 # Fase 2: 10 perkara acak ke validasi.txt untuk dicek manual
python -m src.chunking             # Fase 3: chunk per bagian putusan + penyamaran
python -m src.build_eval           # Fase 4: 82 pertanyaan evaluasi
python -m src.index                # Fase 5: indeks Chroma + BM25
python -m src.eval_retrieval       # Fase 5: Recall@5 dan MRR
python -m src.rag "Berapa vonis dalam perkara 268?"   # Fase 6
python -m src.eval_answers --limit 20                 # Fase 6: akurasi jawaban
streamlit run app.py                                  # Fase 7
```

Di macOS/Linux, aktifkan environment dengan `source .venv/bin/activate` dan salin file dengan `cp`.

`requirements.txt` hanya berisi paket aplikasi (tanpa PyTorch) dan dipakai Streamlit Community Cloud. `requirements-dev.txt` menambahkan PyMuPDF, sentence-transformers, dan Jupyter untuk pengembangan.

## Struktur repo

```text
Dataset-Narkotika-RAG/
├── app.py                   # aplikasi Streamlit
├── data/
│   ├── raw/                 # 51 PDF asli
│   ├── manifest.csv         # file hash -> nomor perkara
│   ├── clean/               # teks bersih per perkara (Fase 1)
│   ├── metadata.db/.csv     # tabel perkara (Fase 2)
│   ├── chunks.jsonl         # chunk + metadata (Fase 3)
│   └── chroma/, bm25.pkl    # indeks (Fase 5)
├── eval/
│   ├── seed_questions.jsonl # 25 pertanyaan manual, kunci dicek ke teks putusan
│   └── questions.jsonl      # 82 pertanyaan evaluasi (Fase 4)
├── notebooks/01_eda.ipynb
└── src/                     # satu modul per tahap pipeline
```

## Hasil evaluasi

| Tahap | Metrik | Hasil |
| --- | --- | --- |
| Retrieval, BM25 saja (69 pertanyaan) | Recall@5 / MRR | 0,71 / 0,42 |
| Retrieval, hibrida + filter nomor (bge-m3) | Recall@5 / MRR | 0,91 / 0,62 |
| Retrieval, vektor + filter nomor (gemini-embedding-001, dipakai untuk deploy) | Recall@5 / MRR | 0,88 / 0,74 |
| Jawaban akhir, evaluasi pertama (82 pertanyaan) | Akurasi / faithfulness | 87% / 77% |
| Jawaban akhir, setelah perbaikan (82 pertanyaan) | Akurasi / faithfulness | 94% / 96% |

Evaluasi jawaban memakai `openai/gpt-oss-20b` via Groq sebagai penjawab dan juri (LLM-as-judge).
Hasil per kategori setelah perbaikan: faktual 95% / 98% (57), naratif 82% / 82% (11), agregat 100% / 100% (11),
di luar data 100% / 100% (3). Hasil evaluasi pertama tersimpan di `eval/hasil_jawaban_v1.csv`.

Keterbatasan: jawaban naratif kadang kurang lengkap dibanding kunci; juri adalah model yang sama dengan penjawab
sehingga bisa bias; `gpt-oss-20b` sesekali kehabisan token saat berpikir, dan panggilan seperti itu diulang
dengan `reasoning_effort=low`.

## Status

| Fase | Isi | Status |
| --- | --- | --- |
| 0 | Persiapan, setup stack, pertanyaan contoh | Kode siap |
| 1 | Ekstraksi dan pembersihan teks | Kode siap |
| 2 | Tabel metadata + EDA | Kode siap |
| 3 | Segmentasi per bagian hukum dan chunking | Kode siap |
| 4 | Dataset evaluasi | Kode siap |
| 5 | Indexing dan retrieval hibrida | Selesai |
| 6 | Generasi, router, evaluasi jawaban | Selesai |
| 7 | Aplikasi dan deployment | on progress |
| 8 | Dokumentasi dan portofolio | |