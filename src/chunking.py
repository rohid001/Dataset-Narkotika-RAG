"""Fase 3: pecah setiap putusan per bagian hukum, potong menjadi chunk, dan samarkan data
pribadi.

Input: data/clean/*.json + data/metadata.csv
Output: data/chunks.jsonl (satu baris JSON per chunk)

Jalankan: python -m src.chunking
"""


import json
import re

import pandas as pd

from src.config import CHUNKS, CLEAN_DIR, DATA_DIR

#--------------------------------------------------Tahap A: segmentasi per bagian hukum

# Urutan bagian dalam putusan dan kalimat yang menandai awalnya.
# Dicari berurutan: penanda bagian ke-n dicari setelah posisi bagian ke-(n-1).
# Bila penanda tidak ditemukan, isinya ikut bagian sebelumnya.
# Bagian pertama, "identitas", selalu mulai di posisi 0 sehingga tidak perlu penanda.

BAGIAN = [
    ("penahanan", r"\nTerdakwa .{0,80}?(?:ditangkap|ditahan|tidak ditahan)"),
    ("tuntutan", r"\nSetelah mendengar (?:pembacaan )?tuntutan"),
    ("pledoi", r"\nSetelah mendengar (?:Nota )?Pembelaan|\nSetelah mendengar (?:pula )?permohonan"),
    ("dakwaan", r"\nMenimbang,? bahwa"),
    ("pembuktian", r"\nMenimbang,? bahwa (?:untuk membuktikan|di ?persidangan Penuntut Umum|Penuntut Umum telah mengajukan)"),
    ("fakta_hukum", r"\nMenimbang,? bahwa berdasarkan .{0,150}?fakta[- ]fakta hukum|\nMenimbang,? bahwa berdasarkan alat bukti"),
    ("pertimbangan_unsur", r"\nMenimbang,? bahwa (?:selanjutnya )?Majelis Hakim (?:akan )?mempertimbangkan"
                            r"|\nMenimbang,? bahwa (:?Para )?Terdakwa (?:telah )?didakwa"),
    ("memberatkan_meringankan", r"\nMenimbang,? bahwa untuk menjatuhkan pidana|\nKeadaan yang memberatkan"),
    ("dasar_hukum", r"\n(?:Memperhatikan|Mengingat),? "),
    ("amar", r"\nMENGADILI:"),
    ("majelis", r"\nDemikian(?:lah)? diputuskan"),
]

def segmentasi(teks: str) -> list[tuple[str, str]]:
    """Kembalikan daftar (nama_bagian, teks_bagian) sesuai urutan di putusan."""
    # 1) cari posisi awal setiap bagian
    batas = [("identitas", 0)]
    pos = 0
    for nama, pola in BAGIAN:
        m = re.search(pola, teks[pos:], re.I)
        if m and nama == "penahanan" and pos + m.start() > 8000: # penahanan selalu di halaman awal
            m = None
        if m:
            awal = pos + m.start()
            batas.append((nama, awal))
            pos = awal + 1
    # 2) potong teks di antara dua posisi berurutan
    hasil = []
    for i, (nama, awal) in enumerate(batas):
        akhir = batas[i + 1][1] if i + 1 < len(batas) else len(teks)
        isi = teks[awal:akhir].strip()
        if isi:
            hasil.append((nama, isi))
    return hasil

#--------------------------------------------------Tahap B: memotong menjadi chunk

TARGET_KATA = 350   # ukuran chunk yang dituju
MAKS_KATA = 450     # paragraf lebih panjang dari ini dipotong per kata
OVERLAP_KATA = 50   # kata terakhir chunk sebelumnya yang dulang di chunk berikutnya

def potong(isi: str) -> list[str]:
    """Gabungkan paragraf sampai sekitar TARGET_KATA, dengan overlap antar-chunk."""
    # 1) ubah setiap paragraf menjadi daftar kata; paragra yang sangat panjang dipecah per MAKS_KATA
    
    paragraf = []
    for par in isi.split("\n"):
        kata = par.split()
        for i in range(0, len(kata), MAKS_KATA):
            paragraf.append(kata[i:i + MAKS_KATA])
            
    # 2) tumpuk paragraf ke chunk; bila chunk akan melewati target, simpan lalu mulai chunk baru
    chunks, sekarang = [], []
    for kata in paragraf:
        if sekarang and len(sekarang) + len(kata) > TARGET_KATA:
            chunks.append(sekarang)
            sekarang = sekarang[-OVERLAP_KATA:]     # chunk baru diawali 50 kata terakhir chunk lama
        sekarang = sekarang + kata
        
    # 3? sisa terakhir disimpaan, kecuali isinya hanya overlap (sudah ada di chunk sebelumnya)
    if sekarang and (not chunks or len(sekarang) > OVERLAP_KATA):
        chunks.append(sekarang)
    return[" ".join(c) for c in chunks]

#--------------------------------------------------Tahap C: penyamaran saksi dan alamat

# Kata yang sering muncul setelah "saksi" tetapi bukan bagian dari nama.
STOP_NAMA = {"Ahli", "Verbalisan", "Mahkota", "Penangkap", "Yang", "Tersebut", "Lainnya",
             "Lain", "Dan", "Bersama", "Para", "Saksi", "Dipersidangan", "Di", "A", "Ade",
             "Telah", "Atas", "Untuk", "Dalam", "Menerangkan", "Terdakwa", "Sebagai", "Adalah",
             "Memberikan"}

# Nama: 1-4 kata yang diawali huruf besar, mis. "Eko Setiadi" atau "RISNAL HARAHAP"
NAMA_RE = r"[A-Z][A-Za-z\.']+(?:\s+[A-Z][A-Za-z\.']+){0,3}"
# "saksi EKO bersama dengan RISNAL, DWI ANSARI dan BUDI": grup 1 = daftar nama setelah "bersama"
BERSAMA_RE = (r"[Ss]aks\s+[A-Z][A-Z\.' ]+?\s+bersama(?:\s+dengan)?\s+"
              r"([A-Z][A-Z\.', ]+?(?:\s+dan\s+[A-Z][A-Z\.' ]+))")

def bersihkan_nama(teks: str) -> str:
    """Buang kata 'alis'/'als' dan kata bukan-nama di depan: 'Verbalisan Eko Setiadi' -> 'Eko Setiadi'."""
    kata = [k for k in teks.replace(",", " ").split() if k.lower().strip(".") not in {"alias", "als"}]
    while kata and kata[0].strip(".") in STOP_NAMA:
        kata = kata[1:]
    return " ".join(kata).strip(" .")

def kunci_nama(nama: str) -> str:
    """Bentuk pembanding: huruf besar, tanpa inisial 1-2 huruf, Y disamakan dengan I (Hery = Heri)."""
    return " ".join(k for k in nama.upper().replace("Y", "I").split() if len(k.strip(".")) > 2)

def kumpulkan_nama_saksi(teks: str, nama_terdakwa: list[str]) -> list[str]:
    """Cari nama saksi, kecuali nama yang juga terdakwa di salah satu perkara.
    
    Sumber nama: (1) kata setelah 'saksi', (2) daftar nama setelah 'saksi X bersama ...'.
    Hasilnya mencakup variasi penulisan (dengan/tanpa inisial).
    """
    calon = set()
    for m in re.finditer(r"[Ss]aksi\s+(" + NAMA_RE + ")", teks):
        calon.add(bersihkan_nama(m.group(1)))
    for m in re.finditer(BERSAMA_RE, teks):
        for bagian in re.split(r",|\s+dan\s+", m.group(1)):
            calon.add(bersihkan_nama(bagian))
    calon = {c for c in calon if len(c) >= 4}
    
    # 2? saring: buang nama terdakwa, simpan nama + varian tanpa inisial
    kunci_terdakwa = [kunci_nama(t) for t in nama_terdakwa]
    hasil, sudah = [], set()
    for nama in sorted(calon, key=lambda n: (-len(n), n)): # urutan tetap: terpanjang dulu, lalu abjad
        dua_kata = " ".join(kunci_nama(nama).split()[:2])
        if not dua_kata or any(dua_kata in t for t in kunci_terdakwa):
            continue        # rekan terdakwa (perkara displit) tetap disebut namanya
        tanpa_inisial = " ".join(w for w in nama.split() if len(w.strip(".")) > 2)
        for varian in (nama, tanpa_inisial):
            if varian.upper() not in sudah and len(varian) >= 4:
                hasil.append(varian)
                sudah.add(varian.upper())
    return hasil

def samarkan(teks: str, nama_saksi: list[str]) -> str:
    """Ganti alamat dengan [ALAMAT] dan nama saksi dengan SAKSI-1, SAKSI-2, ..."""
    # 1) alamat tempat tinggal dan alamat kantor
    teks = re.sub(r"(Tempat tinggal\s*:\s*)[^;\n]+", r"\1[ALAMAT]", teks, flags=re.I)
    teks = re.sub(r"((?:ber)?alamat di\s+)[^,;\n]+", r"\1[ALAMAT]", teks, flags=re.I)
    teks = re.sub(r"(bertempat tinggal di\s+)[^,;\n]+", r"\1[ALAMAT]", teks, flags=re.I)
    # 2) nama saksi; variasi penulisan nama yang sama (kunci_nama sama) mendapat nomor yang sama
    nomor_per_kunci = {}
    for nama in nama_saksi:
        nomor = nomor_per_kunci.setdefault(kunci_nama(nama), len(nomor_per_kunci) + 1)
        pola = r"\s+".join(re.escape(kata) for kata in nama.split()) # spasi ganda di PDF tetap cocok
        teks = re.sub(r"\b" + pola + r"\b", f"SAKSI-{nomor}", teks, flags=re.I)
    return teks

#--------------------------------------------------Tahap D: semua perkara -> chunks.jsonl
def main() -> None:
    meta = pd.read_csv(DATA_DIR / "metadata.csv").set_index("no_urut")
    nama_terdakwa = meta["terdakwa"].dropna().tolist()
    n_chunk, per_bagian = 0, {}
    with open(CHUNKS, "w", encoding = "utf-8") as out:
        for f in sorted(CLEAN_DIR.glob("*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            m = meta.loc[rec["no_urut"]]
            saksi = kumpulkan_nama_saksi(rec["teks"], nama_terdakwa)
            urutan = 0
            for bagian, isi in segmentasi(rec["teks"]):
                for potongan in potong(samarkan(isi, saksi)):
                    urutan += 1
                    chunk = {
                        "id": f"{rec['no_urut']:03d}-{urutan:03d}",
                        "nomor": rec["nomor"],
                        "no_urut": rec["no_urut"],
                        "bagian": bagian,
                        "pasal": m["pasal"],
                        "jenis_narkotika": m["jenis_narkotika"],
                        "vonis_bulan": int(m["vonis_bulan"]),
                        "hakim_ketua": m["hakim_ketua"],
                        "teks": potongan,
                    }
                    out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    n_chunk += 1
                    per_bagian[bagian] = per_bagian.get(bagian, 0) + 1
    print(f"{n_chunk} chunk -> {CHUNKS}")
    for bagian, n in per_bagian.items():
        print(f"    {bagian:<24} {n}")
    
if __name__ == "__main__":
    main()