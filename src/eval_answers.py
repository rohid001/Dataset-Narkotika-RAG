"""Fase 6d: nilai jawaban akhir dengan LLM sebagai juri (LLM-as-judge).

Untuk setiap pertanyaan evaluasi, sistem menjawab, lalu LLM juri menilai:
- benar     : apakah jawaban sesuai kunci jawaban
- didukung  : apakah jawaban didukung sumber yang diambil (faithfulness)
Untuk pertanyaan "di luar data", jawaban dianggap benar bila sistem menyatakan informasinya
tidak tersedia.

jalankan: python -m src.eval_answers --limit 10
(--limit membatasi jumlah pertanyaan supaya hemat kuota; tanpa --limit semua 82 pertanyaan
dipakai)
Hasil disimpen setelah setiap pertanyaan; bila terhenti, menjalankan ulang melanjutkan dari
pertanyaan berikutnya.
Tambahkan --ulang untuk menghupas hasil lama dan mulai dari awal.
"""

import argparse
import json
import re
import time

import pandas as pd
import src.generate as llm      # untuk membaca llm.PROVIDER_TERAKHIR

from src.config import EVAL_DIR
from src.generate import generate
from src.rag import jawab, susun_konteks

HASIL = EVAL_DIR / "hasil_jawaban.csv"

SYSTEM_JURI = "Kamu juri evaluasi yang ketat dan adil. Balas hanya dengan JSON."

PROMPT_JURI = """Pertanyaan: {pertanyaan}
Kunci jawaban: {kunci}
Jawaban sistem: {jawaban}
Sumber yang dipakai sistem:
{sumber}

Nilai jawaban sistem:
- "benar": true bila isi pokok jawaban sistem sesuai kunci jawaban (perbedaan gaya bahasa 
atau detail tambahan yang benar tidak masalah).
Bila kunci menyatakan data tidak tersedia, "benar" = true hanya jika sistem juga menyatakan
informasinya tidak tersedia.
- "didukung": true bila semua fakta di jawaban sistem tercantum di sumber (untuk jawaban
"tidak ditemukan", isi true).
Balas JSON: {{"benar": true/false, "didukung": true/false, "alasan": "satu kalimat"}}
"""

def susun_sumber(hasil: dict) -> str:
    """Sumber untuk juri = persis yang dilihat penjawab: hasil SQL, atau FAKTA TERSTRUKTUR + 
    chunk utuh."""
    if hasil["rute"] == "agregat":
        return f"SQL: {hasil['sql']}\nHasil query:\n{hasil['hasil_sql']}"
    sumber = f"FAKTA TERSTRUKTUR (dari tabel metadata):\n{hasil['fakta']}\n\n" if hasil.get("fakta") else ""
    return sumber + "KONTEKS:\n" + susun_konteks(hasil["sumber"])

def nilai(q: dict, hasil: dict) -> dict:
    """Minta LLM juri menilai satu jawaban. Kembalikan {'benar', 'didukung', 'alasan'}."""
    teks = generate(PROMPT_JURI.format(pertanyaan=q["pertanyaan"], kunci=q["jawaban_kunci"] or "(tidak ada kunci)",
                                       jawaban=hasil["jawaban"], sumber=susun_sumber(hasil)), system=SYSTEM_JURI, temperature=0)
    m = re.search(r"\{.*\}", teks, re.S)    # ambil bagian {...} saja, abaikan teks lain di sekitarnya
    try:
        return json.loads(m.group(0))
    except (AttributeError, json.JSONDecodeError):
        return {"benar": False, "didukung": False, "alasan": "juri tidak membalas JSON: " +
                teks[:150]}
        
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="hanya N pertanyaan pertama")
    ap.add_argument("--jeda", type=float, default=4.0, help="detik jeda antar-pertanyaan (menjaga kuota per menit)")
    ap.add_argument("--ulang", action="store_true", help="hapus hasil lama dan mulai dari awal")
    args = ap.parse_args()
    soal = [json.loads(baris) for baris in open(EVAL_DIR / "questions.jsonl", encoding="utf-8")]
    soal = soal[:args.limit] if args.limit else soal
    
    #lanjutkan dari hasil sebelumnya (bila ada)
    baris = []
    if HASIL.exists() and not args.ulang:
        baris = pd.read_csv(HASIL).to_dict("records")
    sudah = {b["id"] for b in baris}
    
    for i, q in enumerate(soal, 1):
        if q["id"] in sudah:
            continue
        hasil = jawab(q["pertanyaan"])
        penjawab = llm.PROVIDER_TERAKHIR    # gemini / groq, supaya hasil campuran ketahuan
        skor = nilai(q, hasil)
        baris.append({"id": q["id"], "kategori": q["kategori"], "rute": hasil["rute"],
                      "penjawab": penjawab, "juri": llm.PROVIDER_TERAKHIR, "sql": hasil.get("sql", ""),
                      "pertanyaan": q["pertanyaan"], "jawaban": hasil["jawaban"], "kunci": q["jawaban_kunci"],
                      "benar": bool(skor.get("benar")), "didukung": bool(skor.get("didukung")),
                      "alasan": skor.get("alasan", "")})
        pd.DataFrame(baris).to_csv(HASIL, index=False) # simpan setiap pertanyaan, supaya aman bila terhenti
        print(f"{i:>3}/{len(soal)} {q['id']:<5} rute={hasil['rute']:<7} "
              f"benar={baris[-1]['benar']!s:<5} didukung={baris[-1]['didukung']!s:<5} "
              f"[{penjawab}/{llm.PROVIDER_TERAKHIR}]")
        time.sleep(args.jeda)
    df = pd.DataFrame(baris)
    df = df[df.id.isin({q["id"] for q in soal})]    # ringkasan hanya untuk pertanyaan yang diminta
    ringkas = df.groupby("kategori")[["benar", "didukung"]].mean()
    ringkas.loc["SEMUA"] = df[["benar", "didukung"]].mean()
    ringkas["n"] = df.groupby("kategori").size()
    ringkas.loc["SEMUA", "n"] = len(df)
    print(f"\n{len(df)} pertanyaan dinilai -> {HASIL.name}")
    print("Akurasi (benar) dan faithfulness (didukung) per kategori:")
    print(ringkas.to_string(formatters={"benar": "{:.0%}".format, "didukung": "{:.0%}".format, 
                                        "n": "{:.0f}".format}))

if __name__ == "__main__":
    main()