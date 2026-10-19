"""Fase 6b: tentukan rute pertanyaan, dan jawab pertanyaan agregat lewat SQL.

- Pertanyaan agregat ("berapa perkara...", "median vonis...") -> LLM menulis query SQL
ke tabel 'perkara' di data/metadata.db, hasilnya dihitung oleh SQLite (angka pasti benar).
- Selain itu -> RAG (lihat rag.py).

Coba: python -m src.router
"""

import re
import sqlite3
import statistics

from src.config import METADATA_DB
from src.generate import generate
from src.retrieve import nomor_disebut

#----------------------------------------------------------------Tahap A: menentukan rute

KATA_AGREGAT = (r"\b(berapa (?:perkara|putusan|banyak)|median|rata-rata|paling|tertinggi|terendah|terberat|"
                r"teringan|jumlah perkara|perkara mana saja|semua perkara|persen|distribusi|ada berapa)\b")

def rute(pertanyaan: str) -> str:
    """'agregat' bila menanyakan banyak perkara sekaligus dan tidak menyebut satu nomor perkara."""
    if nomor_disebut(pertanyaan):
        return "rag"
    return "agregat" if re.search(KATA_AGREGAT, pertanyaan, re.I) else "rag"

#----------------------------------------------------------------Tahap B: menjalankan SQL dengan aman

class Median:
    """Fungsi agregat MEDIAN untuk SQLite (bawaannya tidak ada): step() per baris, finalize() di akhir."""
    
    def __init__(self):
        self.nilai = []
        
    def step(self, v):
        if v is not None:
            self.nilai.append(v)
    def finalize(self):
        return statistics.median(self.nilai) if self.nilai else None
    
def bersihkan_sql(sql: str) -> str:
    """Buang pagar kode ''''sql ...''' dan titik koma di akhir yang sering ditambahkan LLM."""
    return sql.strip().strip("`").removeprefix("sql").strip().rstrip(";")

def jalankan_sql(sql: str) -> tuple[list[str], list[tuple]]:
    """Jalankan satu query SELECT secara read-only. Kembalikan (nama kolom, baris hasil)."""
    sql = bersihkan_sql(sql)
    if not re.match(r"(?is)^\s*(select|with)\b", sql) or \
        re.search(r"(?i)\b(insert|update|delete|drop|alter|attach|pragma)\b", sql):
        raise ValueError(f"Hanya query SELECT yang diizinkan: {sql}")
    with sqlite3.connect(f"file:{METADATA_DB}?mode=ro", uri=True) as con:
        con.create_aggregate("MEDIAN", 1, Median)
        cur = con.execute(sql)
        kolom = [d[0] for d in cur.description]
        return kolom, cur.fetchmany(60)

#----------------------------------------------------------------Tahap C: pertanyaan agregat -> SQL -> jawaban
SKEMA = """Tabel 'perkara' (satu baris per putusan, 51 baris, semua PN Ranatu Prapat tahun 2023):
- nomor TEXT                contoh '268/Pid.Sus/2023/PN Rap'
- no_urut INTEGER           contoh 268
- n_terdakwa INTEGER        jumlah terdakwa dalam satu putusan
- terdakwa TEXT             nama terdakwa pertama
- umur INTEGER
- pekerjaan TEXT          
- penasihat_hukum INTEGER   1 = didampingi penasihat hukum, 0 = tidak (contoh: WHERE penasihat_hukum = 1)
- pasal TEXT                dasar putusan, contoh '112(1)' atau '114(1), 55(1) KUHP' atau '127(1)a'
- jenis_narkotika TEXT      'sabu', 'ekstasi', atau 'sabu, ganja'
- berat_netto_gram REAL     total berat netto barang bukti narkotika
- tuntutan_bulan INTEGER    tuntutan penjara dari penuntut umum, dalam bulan
- vonis_bula INTEGER        vonis penjara, dalam bulan
- denda_rp INTEGER          
- subsider_bulan INTEGER    pengganti denda bila tidak dibayar, dalam bulan
- bebas_dakwaan_primair INTEGER     1 = dibebaskan dari dakwaan primair tetapi dihukum dakwaan lain
- rehabilitasi INTEGER
- hakim_ketua TEXT
- tgl_musyawarah TEXT, tgl_diucapkan TEXT format '12 Juli 2023'
Fungsi tambahan: MEDIAN(kolom).
Untuk pasal gunakan LIKE, contoh: pasal LIKE '%112(1)%'.
"""

SYSTEM_SQL = ("Kamu menerjemahkan pertanyaan berbahasa Indonesia menjadi SATU query SQLite SELECT."
              "Balas hanya dengan query SQL, tanpa penjelasan dan tanpa ```.")

def jawab_agregat(pertanyaan: str, coba: int = 3 ) -> dict:
    # 1) LLM menulis SQL; bila gagal dijalankan, kirim pesan error-nya dan minta perbaikan (maks. 'coba' kali)
    prompt = f"{SKEMA}\n\nPertanyaan: {pertanyaan}\nSQL:"
    for _ in range(coba):
        sql = generate(prompt, system=SYSTEM_SQL, temperature=0)
        try:
            kolom, baris = jalankan_sql(sql)
            break       # berhasil: keluar dari perulangan
        except Exception as e:
            print(f"    SQL gagal: {e}")
            prompt = (f"{SKEMA}\n\nPertanyaan: {pertanyaan}\nQuery sebelumnya:\n{sql}\nError:{e}\n"
                      "Perbaiki query. SQL:")
    else:       # 'else' milik 'for': jalan bila tidak pernah 'break'
        return {"rute": "agregat", "jawaban": "Maaf, pertanyaan ini belum bisa dijawab dari tabel putusan.",
                "sql": bersihkan_sql(sql), "hasil_sql": "", "sumber": []}
    
    # 2) hasil query ditulis sebagai tabel teks, lalu LLM merangkainya menjadi kalimat
    hasil = "\n".join([" | ".join(kolom)] + [" | ".join(str(x) for x in b) for b in baris])
    jawaban = generate(
        f"Pertanyaan: {pertanyaan}\n\nHasil query dari tabel putusan:\n{hasil}\n\n"
        "Jawab pertanyaan dalam bahasa Indonesia secara singkat berdasarkan hasil query saja."
        "Ubah durasi dalam bulan menjadi tahun dan bulan (mis. 66 bulan = 5 tahun 6 bulan).",
        system="Kamu assiten riset hukum yang teliti. Jangan menambah angka yang tidak ada di hasil query.",
    )
    return {"rute": "agregat", "jawaban": jawaban.strip(), "sql": bersihkan_sql(sql),
            "hasil_sql": hasil, "sumber": []}
    
if __name__ == "__main__":
    hasil = jawab_agregat("Berapa median vonis penjara untuk perkara dengan Pasal 114 ayat (1)?")
    print("SQL      :", hasil["sql"])
    print("Hasil SQL:", hasil["hasil_sql"].replace("\n", " || "))
    print("Jawaban  :", hasil["jawaban"])