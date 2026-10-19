"""Fase 6c: alur tanya-jawab lengkap.

pertanyaan -> rute -> (agregat:SQL) atau (RAG: retrieval -> prompr -> LLM) -> jawaban +
sumber

Coba = python -m src.rag "Berapavonis dalam perkara 268?"
"""

import re
import sqlite3
import sys
from functools import lru_cache

from src.build_eval import fmt_bulan
from src.config import METADATA_DB, RETRIEVAL_MODE
from src.generate import generate
from src.retrieve import cari, nomor_disebut
from src.router import jawab_agregat, rute

#--------------------------------------------------------------Tahap A: bahan prompt

KOLOM_FAKTA = ["nomor", "terdakwa", "pasal", "jenis_narkotika", "berat_netto_gram",
               "tuntutan_bulan", "vonis_bulan", "denda_rp", "subsider_bulan", "hakim_ketua",
               "tgl_musyawarah", "tgl_diucapkan"]

def fakta_terstruktur(no_urut: int) -> str:
    """Baris tabel metadata untuk satu perkara, ditulis sebagai teks."""
    with sqlite3.connect(f"file:{METADATA_DB}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row   # baris diakses lewat nama kolom: row["nomor"]
        row = con.execute(f"SELECT {', '.join(KOLOM_FAKTA)} FROM perkara WHERE no_urut = ?", (no_urut,)).fetchone()
    if not row:
        return ""
    baris = []
    for k in KOLOM_FAKTA:
        v = row[k]
        if v is None:
            continue
        if isinstance(v, float) and v.is_integer(): # 1000000000.0 -> 1000000000 supaya mudah dibaca LLM
            v = int(v)
        if k.endswith("_bulan"):        # 84 -> "84 bulan (7 tahun)" supaya LLM tidak salah hitung
            v = f"{v} bulan" + (f" ({fmt_bulan(v)})" if v >= 12 else "")
        baris.append(f"- {k}: {v}")
    return "\n".join(baris)

@lru_cache(maxsize=1)
def daftar_terdakwa() -> list[tuple[int, str]]:
    """(no_urut, nama terdakwa huruf kecil tanpa alias) untuk setiap perkara."""
    with sqlite3.connect(f"file:{METADATA_DB}?mode=ro", uri=True) as con:
        rows = con.execute("SELECT no_urut, terdakwa FROM perkara").fetchall()
    return [(no, re.split(r"\s+alias\s+", nama, flags=re.I)[0].strip().lower()) for no, nama in rows if nama]

def nomor_dari_nama(pertanyaan: str) -> list[int]:
    """Nomor perkara yang nama terdakwanya disebut di pertanyaan.
    
    Nama satu kata (mis. 'Selamat', 'Gunawan') hanya dihitung bila didahului kata 'terdakwa',
    supaya kata biasa seperti "selamat pagi" tidak ikut cocok.
    """
    teks = pertanyaan.lower()
    nomor = []
    for no, nama in daftar_terdakwa():
        pola = rf"\b{re.escape(nama)}\b" if " " in nama else rf"\bterdakwa\s+{re.escape(nama)}\b"
        if re.search(pola, teks):
            nomor.append(no)
    return nomor

def susun_konteks(chunks: list[dict]) -> str:
    """Chunk diberi nomor [1], [2], ... supaya LLM bisa menyitasinya."""
    return "\n\n".join(f"[{i}] Perkara {c['nomor']} | bagian: {c['bagian']}\n{c['teks']}"
                       for i, c in enumerate(chunks, 1))

#--------------------------------------------------------------Tahap B: menjawab pertanyaan
SYSTEM_RAG = """Kamu adalah asisten riset hukum untuk putusan pidana narkotika Pengadilan 
Negeri Rantau Prapat tahun 2023.
Aturan:
1. Jawab HANYA berdasarkan KONTEKS yang diberikan. Jangan memakai pengetahuan di luar
konteks.
2. Setiap kalimat yang memuat fakta diberi sitasi nomor sumber, contoh: [1] atau [2][3].
3. Bila FAKTA TERSTRUKTUR tersedia, gunakan angka untuk vonis, tuntutan, denda, pasal, dan tanggal.
4. Bila jawabannya tidak ada di konteks, jawab persis: "Informasi tersebut tidak ditemukan
dalam putusan yang tersedia."
5. Jawab dalam bahasa Indonesia yang jelas dan ringkas. Nama yang sudah disamarkan (SAKSI-1,
[ALAMAT]) tulis apa adanya.
6. "Subsider" adalah pidana pengganti bila denda tidak dibayar, BUKAN tambahan pidana penjara.
jangan menjumlahkannya.
7. Pasal dasar putusan adalah pasal yang dinyatakan terbukti di amar putusan (kolom pasal di 
FAKTA TERSTRUKTUR), bukan pasal dakwaan primair.
"""
def jawab(pertanyaan: str, k: int= 6) -> dict:
    if rute(pertanyaan) == "agregat":
        return jawab_agregat(pertanyaan)
    
    chunks = cari(pertanyaan, k=k, mode=RETRIEVAL_MODE)
    nomor = nomor_disebut(pertanyaan) or nomor_dari_nama(pertanyaan) # nomor perkara, atau nama terdakwa
    fakta = "\n\n".join(f for f in (fakta_terstruktur(n) for n in nomor) if f)
    prompt = ""
    if fakta:
        prompt += f"FAKTA TERSTRUKTUR (dari tabel metadata):\n{fakta}\n\n"
    prompt += f"KONTEKS:\n{susun_konteks(chunks)}\n\nPERTANYAAN: {pertanyaan}\n\nJAWABAN:"
    jawaban = generate(prompt, system=SYSTEM_RAG)
    return {"rute": "rag", "jawaban": jawaban.strip(), "sumber": chunks, "fakta": fakta}
    
if __name__ == "__main__":
    tanya = " ".join(sys.argv[1:]) or "Berapa vonis dan denda dalam perkara 268?"
    hasil = jawab(tanya)
    print(f"[rute: {hasil['rute']}]\n{hasil['jawaban']}\n")
    if hasil.get("sql"):
        print("SQL:", hasil["sql"])
    for i, c in enumerate(hasil["sumber"], 1):
        print(f"[{i}] {c['nomor']} | {c['bagian']}")