"""Fase 4: susun dataset evaluasi dari 3 sumber.

1. eval/seed_questions.jsonl -> 20 pertanyaan manual dari Fase 0 (sudah dicek ke teks putusan)
2. pertanyaan faktual otomatis -> satu per perkara, kunci jawaban dari tabel metadata
3. pertanyaan agregat otomatis -> jawaban dihitung dengan pandas dari tabel metadata

Output: eval/questions.jsonl

Jalankan: python -m src.build_eval
"""

import json
import re
import pandas as pd

from src.config import DATA_DIR, EVAL_DIR

#---------------------------------------------------------------Tahap A: format jawaban dan template

def fmt_bulan(bulan: float) -> str:
    """66 -> '5 tahun 6 bulan', 48 -> '4 tahun', 6 '6 bulan'."""
    tahun, sisa = divmod(int(bulan), 12)
    bagian = []
    if tahun:
        bagian.append(f"{tahun} tahun")
    if sisa:
        bagian.append(f"{sisa} bulan")
    return " ".join(bagian)

def fmt_gram(gram: float) -> str:
    """0.33 -> '0,33 gram netto' (desimal memakai koma seperti di putusan)."""
    return f"{gram:g} gram netto".replace(".", ",")

# Setiap template: (kalimat pertanyaan, kolom jawaban, bagian putusan yang memuat jawabannya, cara menulis jawaban)
TEMPLATE = [
    ("Berapa lama pidana penjara yang dijatuhkan dalam {ref}?", "vonis_bulan", ["amar"], fmt_bulan),
    ("Siapa hakim ketua dalam {ref}?", "hakim_ketua", ["majelis"], str),
    ("Pasal apa yang menjadi dasar putusan dalam {ref}?", "pasal", ["dasar_hukum", "amar"], str),
    ("Berapa tuntutan pidana penjara dari penuntut umum dalam {ref}?", "tuntutan_bulan", ["tuntutan"], fmt_bulan),
    ("Kapan putusan {ref} diucapkan dalam sidang terbuka?", "tgl_diucapkan", ["majelis"], str),
    ("Berapa berat netto narkotika yang menjadi barang bukti dalam {ref}?", "berat_netto_gram", ["amar"], fmt_gram)
]

#---------------------------------------------------------------Tahap B: pertanyaan faktual per perkara

def faktual_otomatis(df: pd.DataFrame) -> list[dict]:
    """Satu pertanyaan per perkara; template dipakai bergiliran supaya jenis pertanyaan merata."""
    hasil = []
    for i, row in enumerate(df.itertuples()):
        tanya, kolom, bagian, tulis = TEMPLATE[i % len(TEMPLATE)]
        nilai = getattr(row, kolom)
        if pd.isna(nilai):  # kolom kosong (mis. berat netto) -> pakai template vonis
            tanya, kolom, bagian, tulis = TEMPLATE[0]
            nilai = row.vonis_bulan
        
        # Sepertiga pertanyaan menyebut nama terdakwa, bukan nomor perkara,
        # untuk menguji retrieval tanpa bantuan filter nomor.
        if i % 3 == 2:
            nama = re.split(r" alias", str(row.terdakwa), flags=re.I)[0].title()
            ref = f"perkara terdakwa {nama}"
        else:
            ref = f"perkara {row.nomor}"
        
        hasil.append({
            "kategori": "faktual",
            "pertanyaan": tanya.format(ref=ref),
            "jawaban_kunci": tulis(nilai),
            "perkara": [row.nomor],
            "bagian": bagian,
            "sumber": "otomatis",
        })
        
    return hasil

#---------------------------------------------------------------Tahap C: pertanyaan agregat

def agregat_otomatis(df:pd.DataFrame)-> list[dict]:
    """Pertanyaan statistik lintas perkara; jawaban dihitung pandas, jadi pasti benar."""
    hakim = df.hakim_ketua.value_counts()   # jumlah perkara per hakim, terbanyak dulu (descanding)
    p114 = df[df.pasal.str.contains("114(1)", regex=False)]  # perkara dengan Pasal 114 ayat (1)
    rasio = (df.vonis_bulan / df.tuntutan_bulan).median()   #vonis dibagi tuntutan, per perkara
    ganja = df[df.jenis_narkotika.str.contains("ganja")]
    termurah = df.loc[df.vonis_bulan.idxmin()]  # baris dengan vonis paling ringan
    
    data = [
        ("Siapa hakim ketua yang paling banyak memimpin perkara dan berapa jumlahnya?",
         f"{hakim.index[0]}, {hakim.iloc[0]} perkara."),
        ("Berapa median vonis penjara untuk perkara dengan Pasal 114 ayat (1)?",
         f"{fmt_bulan(p114.vonis_bulan.median())}, dari {len(p114)} perkara."),
        ("Berapa perkara yang terdakwanya didampingi penasihat hukum?",
         f"{int(df.penasihat_hukum.sum())} dari {len(df)} perkara."),
        ("Secara median, vonis hakim berapa persen dari tuntuan penuntut umum?", 
         f"Sektiar {rasio:.0%}."),
        ("Perkara mana saja yang barang buktinya mencakup ganja?",
         ", ".join(ganja.nomor) + "."),
        ("Berapa vonis penjara paling ringan dalam dataset dan di perkara mana?",
         f"{fmt_bulan(termurah.vonis_bulan)}, perkara {termurah.nomor}."),
    ]
    hasil = []
    for pertanyaan, jawaban in data:
        hasil.append({
            "kategori": "agregat",
            "pertanyaan": pertanyaan,
            "jawaban_kunci": jawaban,
            "perkara": [],  # kosong: jawabannya dari tabel, bukan dari satu putusan
            "bagian": [],
            "sumber": "otomatis",
        })
    return hasil

#---------------------------------------------------------------Tahap D: gabungkan dan simpan

def main() -> None:
    df = pd.read_csv(DATA_DIR / "metadata.csv").sort_values("no_urut")
    seed = [json.loads(baris) for baris in open(EVAL_DIR / "seed_questions.jsonl", encoding="utf-8")]
    for q in seed:
        q["sumber"] = "manual"
        
    semua = seed + faktual_otomatis(df) + agregat_otomatis(df)
    with open(EVAL_DIR / "questions.jsonl", "w", encoding="utf-8") as fh:
        for i, q in enumerate(semua, 1):
            if "id" not in q:   # pertanyaan otomatis diberi id A021, A022, ...
                    q = {"id": f"A{i:03d}", **q}
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
        
    print(f"{len(semua)} pertanyaan -> eval/questions.jsonl")
    print(pd.Series([q["kategori"] for q in semua]).value_counts().to_string())

if __name__ == "__main__":
    main()