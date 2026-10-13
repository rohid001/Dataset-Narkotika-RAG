"""Fase 5c: ukur kualitas retrieval dengan Recall@5 dan MRR.

Sebuah pertanyaan dianggap "kena" bila salah satu dari 5 chunk teratas berasal dari
perkara yang benar DAN dari bagian putusan yang memuat jawabannya.

- Recall@5  : presentase pertanyaan yang kena di 5 besar
- MRR       : rata-rata 1/peringkat chunk benar pertama (1,0 = selalu di peringkat 1)

Jalankan python -m src.eval_retrieval
Hasil disimpan per model: eval/hasil_retrieval_<model>.csv
"""
import json
import re
import pandas as pd

from src.config import EMBEDDING_MODEL, EVAL_DIR
from src.retrieve import cari

# (nama baris di tabel, mode pencarian, pakai filter nomor perkara?)
KONFIGURASI = [
    ("vektor", "vektor", False),
    ("vektor + filter nomor", "vektor", True),
    ("bm25", "bm25", False),
    ("hibrida", "hibrida", False),
    ("hibrida + filter nomor", "hibrida", True)
]

def benar(chunk: dict, q: dict) -> bool:
    """Chunk dianggap benar bila perkaranya tepat dan bagiannya termasuk bagian kunci."""
    return chunk["nomor"] in q["perkara"] and (not q["bagian"] or chunk["bagian"] in q["bagian"])

def main(k: int=5) -> pd.DataFrame:
    soal = [json.loads(baris) for baris in open(EVAL_DIR / "questions.jsonl", encoding="utf-8")]
    soal = [q for q in soal if q["perkara"]]    # agregat & di luar data tidak diuji di retrieval
    
    baris = []
    for nama, mode, pakai_filter in KONFIGURASI:
        kena, rr = [], []
        for q in soal:
            hasil = cari(q["pertanyaan"], k=k, mode=mode, pakai_filter=pakai_filter)
            # peringkat (1, 2, ...) chunk benar pertama; None bila tidak ada di k besar
            posisi = next((i for i, c in enumerate(hasil, 1) if benar(c, q)), None)
            kena.append(posisi is not None)
            rr.append(1 / posisi if posisi else 0)
        baris.append({"konfigurasi": nama, f"Recall@{k}": sum(kena) / len(soal), "MRR":sum(rr) / len(soal)})
        
    tabel = pd.DataFrame(baris)
    print(f"Model {EMBEDDING_MODEL}, {len(soal)} pertanyaan diuji\n")
    print(tabel.to_string(index=False, float_format="{:.3f}".format))
        
    nama_file = "hasil_retrieval_" + re.sub(r"[^a-z0-9]+", "-", EMBEDDING_MODEL.lower()) + ".csv"
    tabel.to_csv(EVAL_DIR / nama_file, index=False)
    print(f"\nDisimpan ke eval/{nama_file}")
    return tabel

if __name__== "__main__":
    main()