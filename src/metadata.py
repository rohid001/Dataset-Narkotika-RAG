"""Fase 2: ekstrak metadata terstruktur dari setiap putusan ke tabel.

Input: data/clean/*.json
Output: data/metadata.db (SQLite, tabel 'perkara') dan data/metadata.csv

Jalankan: python -m src.metadata
Cek manual: python -m src.metadata --sampai 10 (hasil di validasi.txt)
"""

import argparse
import json
import re
import sqlite3

import pandas as pd

from src.config import CLEAN_DIR, DATA_DIR, METADATA_DB

# ------------------------------------------------------Tahap A: alat bantu

# "4 (empat) Tahun" atau "4 (empat) Tahun 6 (enam) Bulan" / "..., 6 (enam) Bulan" / "... & 6 (enam) bulan"
DURASI_RE = re.compile(
    r"(\d+)\s*\([^)]*\)\s*(tahun|bulan)"
    r"(?:[,\s]+(?:dan\s+|&\s+)?(\d+)\s*\([^)]*\)\s*bulan)?",
    re.I,
)
# "12 Juli 2023"
TANGGAL = r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})"

def durasi_bulan(text: str) -> int | None:
    """'4 (empat) Tahun 6 (enam) bulan' -> 54. None bila tidak ada durasi"""
    m = DURASI_RE.search(text)
    if not m:
        return None
    angka = int(m.group(1))
    satuan = m.group(2).lower()
    tambahan = m.group(3)
    bulan = angka * 12 if satuan == "tahun" else angka
    if tambahan:
        bulan += int(tambahan)
    return bulan

def cari(pola: str, text: str, flags=re.I | re.S) -> str | None:
    """Ambil grup pertama dari pola, dengan spasi dirapikan. None bila tidak ketemu."""
    m = re.search(pola, text, flags)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()

# ------------------------------------------------------Tahap B: memotong bagian putusan

def bagian_amar(teks: str) -> str:
    """Teks dari 'MENGADILI:' terakhir sapai akhir dokumen."""
    return teks[teks.rfind("MENGADILI:"):]

def bagian_tuntutan(teks: str) -> str:
    """Tuntutan dibacakan sebelum pertimbangan hakim: ambil teks sebelum 'Menimbang' pertama."""
    akhir = teks.find("Menimbang")
    return teks[:akhir] if akhir > 0 else ""

def bagian_dasar_hukum(teks: str) -> str:
    """Paragraf 'Memperhatikan'/'Mengingat' tepat sebelum amar: pasal yang dipakai hakim."""
    i_amar = teks.rfind("MENGADILI:")
    i_dasar = max(teks.rfind("Memperhatikan", 0, i_amar), teks.rfind("Mengingat", 0, i_amar))
    return teks[i_dasar:i_amar] if i_dasar >= 0 else ""

def bagian_penutup(teks: str) -> str:
    """Paragraf 'Demikian diputuskan ...': berisi tanggal dan susunan majelis hakim."""
    return cari(r"(Demikian(?:lah)? diputuskan.{0,700})", teks) or ""

def pidana_penjara(segmen: str) -> int | None:
    """Durasi penjara pertama setelah frasa 'Menjatuhkan pidana'."""
    i = segmen.find("Menjatuhkan pidana")
    if i < 0:
        i = segmen.find("pidana penjara")
    if i < 0:
        return None
    return durasi_bulan(segmen[i:i + 400])

# ------------------------------------------------------Tahap C: satu fungsi per kolom

def ambil_pasal(dasar: str) -> str:
    """'Pasal 112 Ayat (1) ... Jo Pasal 55 Ayat (1) KUHP' -> '112(1), 55(1) KUHP'."""
    pola = r"Pasal\s+(\d+)\s*(?:ayat)?\s*\((\d)\)(?:\s*huruf\s*([a-z]))?(?=(.{0,40}))"
    pasal = []
    
    for m in re.finditer(pola, dasar, re.I):
        label = f"{m.group(1)}({m.group(2)})"
        if m.group(3):
            label += m.group(3)     # huruf. mis. 127(1)a
        if "KUHP" in m.group(4):
            label += " KUHP"
        if label not in pasal:
            pasal.append(label)
    return ", ".join(pasal)

def ambil_jenis_narkotika(amar: str) -> str:
    """Jensi narkotika yang disebut di amar: 'sabu', 'ekstasi', atau 'sabu, ganja'."""
    amar = amar.lower()
    kamus = [
        ("sabu", ["sabu", "shabu", "metamfetamin"]),
        ("ganja", ["ganja"]),
        ("ekstaksi", ["ekstasi", "ekstasy", "ecstasy"])
    ]
    jenis = []
    for nama, kata_kata in kamus:
        if any(kata in amar for kata in kata_kata):
            jenis.append(nama)
    return ", ".join(jenis)

def ambil_berat_netto(amar: str) -> float | None:
    """Jumlah semua berat 'netto' di amar, dalam gram. None bila hanya ada berat bruto."""
    pola = (r"(\d+(?:[,.]\s?\d+)?)\s*(?:\([^)]*\))?\s*(?:gram|gr)\.?\s*/?\s*netto" # "0,33 (..) gram netto"
            r"|(?<=netto )(\d+(?:[,.]\s?\d+)?)\s*(?:\([^)]*\))?\s*(?:gram|gr)\b") # "netto 1,45 (..) gram"
    berat = []
    for m in re.finditer(pola, amar, re.I):
        angka = m.group(1) or m.group(2)
        berat.append(float(angka.replace(" ", "").replace(",", ".")))
    return round(sum(berat), 2) if berat else None

def hitung_terdakwa(amar: str) -> int:
    if re.search(r"Terdakwa III\b", amar):
        return 3
    if re.search(r"Terdakwa II\b|Para Terdakwa", amar):
        return 2
    return 1

def ambil_tanggal(penutup: str) -> tuple[str | None, str | None]:
    """(tanggal musyawarah, tanggal diucapkan). Keduanya sering berbeda."""
    musyawarah = cari(r"tanggal\s+" + TANGGAL, penutup, re.S)
    diucapkan = cari(r"diucapkan.{0,120}?tanggal\s+" + TANGGAL, penutup, re.S)
    if not diucapkan and "itu juga" in penutup:     # "... diucapkan pada hari itu juga"
        diucapkan = musyawarah
    return musyawarah, diucapkan

def ambil_umur(kepala: str) -> int | None:
    umur = cari(r"Umur\s*/?\s*tanggal\s?lahir\s*:\s*(\d+)\s*(?:tahun|/)", kepala)
    return int(umur) if umur else None

def ekstrak(rec: dict) -> dict:
    """Satu perkara (hasil Fase 1) -> satu baris tabel."""
    teks = rec["teks"]
    kepala = teks[:12000]   # bagian identitas terdakwa
    amar = bagian_amar(teks)
    penutup = bagian_penutup(teks)
    tgl_musyawarah, tgl_diucapkan = ambil_tanggal(penutup)
    denda = cari(r"denda\s+(?:sejumlah|sebesar|sejumah)\s+Rp\.?\s?([\d\.]+)", amar)
    subsider = cari(r"tidak dibayar.{0,60}?pidana (?:penjara|kurungan)\s+(?:selama\s+)?(.{0,40})", amar)
    didampingi = bool(re.search(r"didampingi (?:oleh )?Penasi?e?hat Hukum", kepala, re.I))
    tidak_didampingi = bool(re.search(r"tidak didampingi", kepala, re.I))
    
    return {
        "nomor": rec["nomor"],
        "no_urut": rec["no_urut"],
        "file": rec["file"],
        "halaman": rec["halaman"],
        "n_kata": rec["n_kata"],
        "n_terdakwa": hitung_terdakwa(amar),
        "terdakwa": cari(r"Nama lengkap\s*:\s*(.+?)(?:;|\s\d+\.\s*Tempat|\n\d+\.)", kepala),
        "umur": ambil_umur(kepala),
        "pekerjaan": cari(r"Pekerjaan\s*:\s*(.+?)(?:;|\n)", kepala),
        "penasihat_hukum": didampingi and not tidak_didampingi,
        "pasal": ambil_pasal(bagian_dasar_hukum(teks)),
        "jenis_narkotika": ambil_jenis_narkotika(amar),
        "berat_netto_gram": ambil_berat_netto(amar),
        "tuntutan_bulan": pidana_penjara(bagian_tuntutan(teks)),
        "vonis_bulan": pidana_penjara(amar),
        "denda_rp": int(denda.replace(".", "")) if denda else None,
        "subsider_bulan": durasi_bulan(subsider) if subsider else None,
        "bebas_dakwaan_primair": bool(re.search(r"Membebaskan (?:Para )?Terdakwa.{0,40}dari Dakwaan", amar, re.I | re.S)),
        "rehabilitasi": "rehabilitasi" in amar.lower(),
        "hakim_ketua": cari(r"([A-Z][A-Za-z\.' ]+?),\s*S\.\s?H\..{0,25}?(?:sebagai|selaku)\s+Hakim Ketua", penutup, re.S),
        "tgl_musyawarah": tgl_musyawarah,
        "tgl_diucapkan": tgl_diucapkan,
    }
    
# ------------------------------------------------------Tahap D: simpan dan validasi

def tampilkan_sampel(n: int) -> None:
    """Tulis hasil parser + awal amar untuk n perkara acak ke validasi.txt, untuk dicek manual ke PDF."""
    df = pd.read_csv(DATA_DIR / "metadata.csv")
    baris = []
    for _, row in df.sample(n, random_state=42).iterrows():
        rec = json.loads((CLEAN_DIR / f"{row.no_urut:03d}.json").read_text(encoding="utf-8"))
        amar = bagian_amar(rec["teks"])
        baris.append("=" * 80)
        baris.append(f"{row.nomor}  (file PDF: {row.file})")
        for kolom in ["terdakwa", "pasal", "jenis_narkotika", "berat_netto_gram", "tuntutan_bulan",
                      "vonis_bulan", "denda_rp", "subsider_bulan", "hakim_ketua", "tgl_diucapkan"]:
            baris.append(f"  {kolom:<18}: {row[kolom]}")
        baris.append("  --- awal amar ---")
        baris.append("  " + amar[:700].replace("\n", "\n  "))
    # ditulis langsung sebagai UTF-8 (pengalihan ">" di PowerShell 5.1 mengubah encoding file)
    out = DATA_DIR.parent / "validasi.txt"
    out.write_text("\n".join(baris) + "\n", encoding="utf-8")
    print(f"{n} perkara sampel ditulis ke {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sampel", type=int, default=0, help="tulis N perkara acak ke validasi.txt untuk dicek manual")
    args = ap.parse_args()
    if args.sampel:
        tampilkan_sampel(args.sampel)
        return

    rows = []
    for f in sorted(CLEAN_DIR.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        rows.append(ekstrak(rec))
    df = pd.DataFrame(rows).sort_values("no_urut")

    with sqlite3.connect(METADATA_DB) as con:
        df.to_sql("perkara", con, if_exists="replace", index=False)
    df.to_csv(DATA_DIR / "metadata.csv", index=False)

    print(f"{len(df)} perkara -> {METADATA_DB.name} dan metadata.csv")
    print("Kolom yang masih kosong (jumlah perkara):")
    kosong = df.isna().sum()
    print(kosong[kosong > 0].to_string() if kosong.any() else "  tidak ada")
        
if __name__ == "__main__":
    main()
