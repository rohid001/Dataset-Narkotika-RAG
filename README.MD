# RAG Putusan Narkotika PN Rantau Prapat

Asisten tanya-jawab berbasis *Retrieval-Augmented Generation* (RAG) di atas 51 putusan pidana narkotika Pengadilan Negeri Rantau Prapat tahun 2023. Setiap jawaban wajib menyebut nomor perkara dan bagian putusan yang menjadi sumbernya.

Project ini adalah pengembangan dari [Dataset-Narkotika_092_074](https://github.com/rohid001/Dataset-Narkotika_092_074).

## Tujuan

Pertanyaan yang harus bisa dijawab terbagi dua:

- **Naratif dan faktual per perkara**, misalnya "bagaimana kronologi penangkapan di perkara 268?". Dijawab dengan RAG: cari potongan putusan yang relevan, lalu LLM menyusun jawaban dari potongan itu.
- **Agregat lintas perkara**, misalnya "berapa median vonis Pasal 112 ayat (1)?". Dijawab dengan query ke tabel metadata perkara, bukan dengan RAG, supaya angkanya pasti benar.

## Dataset

| Atribut | Nilai |
| --- | --- |
| Sumber | Direktori Putusan Mahkamah Agung RI (putusan.mahkamahagung.go.id) |
| Pengadilan | PN Rantau Prapat (`PN Rap`), tingkat pertama |
| Jumlah putusan | 51 (nomor perkara unik, tanpa duplikat) |
| Jenis perkara | `Pid.Sus`, tahun 2023, diputus Juni–Oktober 2023 |
| Ukuran | 1.333 halaman PDF, sekitar 408 ribu kata setelah noise dibuang |
| Narkotika | Sabu di hampir semua perkara; ekstasi di 235; sabu + ganja di 310 |
| Format | PDF dengan lapisan teks (tanpa OCR); nama file berupa hash |

`data/manifest.csv` memetakan setiap nama file hash ke nomor perkaranya, beserta jumlah halaman dan checksum SHA-256.

### Batasan

- Hanya satu pengadilan dan satu tahun, jadi hasilnya tidak bisa digeneralisasi ke pengadilan atau periode lain.
- Hanya putusan tingkat pertama; tidak ada putusan banding atau kasasi.
- Putusan memuat nama, umur, dan alamat terdakwa serta saksi. Di aplikasi, nama saksi dan alamat disamarkan; nama terdakwa tetap ditampilkan karena putusan bersifat publik.

## Keputusan desain (Fase 0)

| Topik | Keputusan |
| --- | --- |
| LLM | Lewat API, dibungkus satu fungsi `generate()` agar bisa diganti ke model lokal. Provider dipilih di Fase 6. |
| Data pribadi | Nama saksi dan alamat disamarkan; nama terdakwa tetap. |
| Framework | Python murni + Chroma (vektor) + rank-bm25 (kata kunci), tanpa LangChain/LlamaIndex. |
| Embedding | Model multilingual, default `BAAI/bge-m3` (bisa diganti lewat `.env`). |

## Pertanyaan contoh

20 pertanyaan di [`eval/seed_questions.jsonl`](eval/seed_questions.jsonl) menjadi patokan arah sistem dan bibit dataset evaluasi Fase 4. Kunci jawaban per perkara sudah dicek manual ke teks putusan. Hitungan agregat masih sementara dan akan dikunci ulang dari tabel metadata di Fase 2.

| ID | Kategori | Pertanyaan |
| --- | --- | --- |
| Q01 | Naratif | Bagaimana kronologi penangkapan terdakwa dalam perkara 268? |
| Q02 | Naratif | Mengapa terdakwa perkara 105 dibebaskan dari dakwaan primair tetapi tetap dipidana? |
| Q03 | Naratif | Apa saja keadaan yang memberatkan dan meringankan terdakwa perkara 268? |
| Q04 | Naratif | Apa hubungan antara perkara 417, 418, dan 419? |
| Q05 | Naratif | Mengapa hakim perkara 325 menerapkan Pasal 127, bukan Pasal 112 jo 132 seperti tuntutan? |
| Q06 | Naratif | Barang bukti narkotika apa saja yang disita dalam perkara 310? |
| Q07 | Faktual | Berapa vonis, denda, dan tuntutan dalam perkara 268? |
| Q08 | Faktual | Berapa berat sabu yang menjadi barang bukti perkara 105? |
| Q09 | Faktual | Siapa hakim ketua perkara 509 dan kapan putusannya diucapkan? |
| Q10 | Faktual | Berapa tuntutan dan vonis para terdakwa perkara 325? |
| Q11 | Faktual | Jenis dan berat narkotika apa yang menjadi barang bukti perkara 235? |
| Q12 | Faktual | Pasal apa yang terbukti dalam perkara 406 dan berapa vonisnya? |
| Q13 | Agregat | Berapa perkara yang diketuai hakim Hendrik Tarigan? |
| Q14 | Agregat | Berapa perkara yang terdakwanya dibebaskan dari dakwaan primair tetapi dihukum dengan dakwaan lain? |
| Q15 | Agregat | Berapa vonis penjara tertinggi dan di perkara mana? |
| Q16 | Agregat | Ada berapa putusan dengan lebih dari satu terdakwa? |
| Q17 | Agregat | Berapa median vonis penjara untuk perkara Pasal 112 ayat (1)? |
| Q18 | Di luar data | Berapa vonis perkara narkotika di PN Medan tahun 2023? |
| Q19 | Di luar data | Apa putusan banding untuk perkara 310? |
| Q20 | Di luar data | Bagaimana tren vonis narkotika di PN Rantau Prapat 2021–2024? |

Untuk tiga pertanyaan terakhir, jawaban yang benar adalah menyatakan bahwa data tidak tersedia, bukan mengarang jawaban.

## Catatan dari pengecekan awal

Temuan ini perlu ditangani di fase berikutnya:

- **Tanggal putusan ada dua:** tanggal musyawarah majelis dan tanggal putusan diucapkan sering berbeda (misalnya perkara 310: diputus 25 Juli 2023, diucapkan 3 Agustus 2023). Tabel metadata perlu menyimpan keduanya.
- **"Dibebaskan dari dakwaan primair" bukan vonis bebas.** Di 17 perkara terdakwa tetap dipidana lewat dakwaan subsidair atau alternatif. Tidak ada vonis bebas murni dan tidak ada putusan rehabilitasi.
- **Kalimat "bertempat di" yang pertama kali muncul** kadang berisi alamat penasihat hukum, bukan lokasi kejadian.
- **Variasi format:** "MENGADILI" kadang ditulis berspasi ("M E N G A D I L I") dan kadang tanpa titik dua; vonis ditulis "pidana penjara masing-masing selama ..." untuk terdakwa lebih dari satu.

## Struktur repo

```text
Dataset-Narkotika-RAG/
├── data/
│   ├── raw/             # 51 PDF asli
│   ├── manifest.csv     # file hash -> nomor perkara
│   └── clean/           # JSON teks bersih per perkara (Fase 1)
├── src/
│   ├── config.py        # path dan variabel lingkungan
│   └── build_manifest.py
├── eval/
│   └── seed_questions.jsonl
├── notebooks/
├── requirements.txt
└── .env.example
```

## Menjalankan

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # isi kunci API saat Fase 6
python -m src.build_manifest       # membuat ulang data/manifest.csv
```

## Status

| Fase | Isi | Status |
| --- | --- | --- |
| 0 | Scoping, pertanyaan contoh, kerangka repo | Selesai |
| 1 | Ekstraksi dan pembersihan teks | Berikutnya |
| 2 | Tabel metadata perkara + EDA | |
| 3 | Segmentasi per bagian hukum dan chunking | |
| 4 | Dataset evaluasi | |
| 5 | Indexing dan retrieval hibrida | |
| 6 | Generasi dan router | |
| 7 | Aplikasi dan deployment | |
| 8 | Dokumentasi dan portofolio | |
