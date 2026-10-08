"""Fase 1: ekstrak teks dari 51 PDF putusan dari bersihkan noise.

Input : data/raw/*.pdf + data/manifest.csv
Output : data/clean/<no_urut>.json, satu file per perkara

Jalankan: python -m src.extract
"""

import csv
import json
import re

import pymupdf

from src.config import CLEAN_DIR, MANIFEST, RAW_DIR

# Baris yang selalu muncul di setiap halaman dan tidak ada hubungannya dengan isi putusan.
NOISE_PATTERNS = [
    r"Direktori Putusan Mahkamah Agung Republik( Indonesia)?",
    r"Indonesia",
    r"putusan\.mahkamahagung\.go\.id",
    r"Disclaimer",
    r"Kepaniteraan Mahkamah Agung Republik Indonesia berusaha.*",
    r"pelaksanaan fungsi peradilan\..*",
    r"Dalam hal Anda menemukan inakurasi.*",
    r"Email : kepaniteraan@.*",
    r"Halaman \d+",
    r"Halaman \d+ dari \d+ Putusan Nomor .*",
    r"Pid\.[A-Z]\.[A-Z0-9\.]+",          # kode klasifikasi, mis. Pid.I.A.1.3
]
NOISE_RE = re.compile(r"^\s*(?:" + "|".join(NOISE_PATTERNS) + r")\s*$")

# Simbol bullet dari PDF (sebagian tak terlihat di layar), ditulis sebagai kode Unicode-nya.
BULLETS = "".join(chr(kode) for kode in (0x2022, 0xF02D, 0xF0B7, 0xF0D8))


def clean_page(raw: str) -> list[str]:
    """Buang baris noise dan rapikan spasi; hasilnya daftar baris yang bermakna."""
    lines = []
    for line in raw.splitlines():
        line = re.sub(f"[{BULLETS}]", "-", line)       # simbol bullet PDF -> "-"
        line = re.sub(r"\s+", " ", line).strip()
        if line and not NOISE_RE.match(line):
            lines.append(line)
    return lines

# Penanda daftar yang berdiri sendiri di satu baris: "1.", "a.", atay "-"
LIST_MARKER_RE = re.compile(r"^(\d{1,2}\.|[a-z]\.|-)$")
# Kalimat yang menandai awal paragraf baru di putuasan.
PARA_START_RE = re.compile(
    r"^(Menimbang|Mengingat|Memperhatikan|Setelah|MENGADILI|M E N G A D I L I|Demikian|"
    r"Dakwaan|Keadaan yang|Terdakwa (ditangkap|ditahan|didampingi))"
)

def join_lines(lines: list[str]) -> str:
    """Sambung baris yang terpotong menjadi paragraf utuh.
    
    Baris baru dipertahankan bila baris sebelumnya diakhiri ';' atau ':',
    atau bila baris ini membuka paragraf baru (Menimbang, MENGADILI, dst.).
    """
    
    out = ""
    pending_marker = ""
    for line in lines:
        if LIST_MARKER_RE.match(line):
            pending_marker = line + " "
            continue
        piece = pending_marker + line
        new_para = bool(pending_marker) or not out or out.endswith((";", ":")) or PARA_START_RE.match(line)
        out += ("\n" if new_para and out else " " if out else "") + piece
        pending_marker = ""
    return out

def normalize(text: str) -> str:
    # footer yang kadang menempel di tengah kalimat, mis. "setidakHalaman 3 dari 31 Putusan Nomor ..."
    text = re.sub(r"Halaman \d+ dari \d+ Putusan Nomor \d+/Pid\.[\w\.\-]+/\d{4}/PN Rap", "", text)
    text = re.sub(r"M\s?E\s?N\s?G\s?A\s?D\s?I\s?L\s?I\s*:?", "MENGADILI:", text)
    text = re.sub(r" +", " ", text)
    return text.strip()

def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = list(csv.DictReader(fh))
        
    total_raw = total_clean = 0
    for row in manifest:
        offsets, raw_len, teks= [], 0, ""
        with pymupdf.open(RAW_DIR / row["file"]) as doc:
            for page in doc:
                raw = page.get_text()
                raw_len += len(raw)
                page_text = normalize(join_lines(clean_page(raw)))
                offsets.append(len(teks)) # Posisi awal halaman ini di 'teks'
                teks += page_text + "\n"
        teks = teks.strip()
        total_raw += raw_len
        total_clean += len(teks)
        record = {
            "nomor": row["nomor"],
            "no_urut": int(row["no_urut"]),
            "file": row["file"],
            "halaman": int(row["halaman"]),
            "awal_halaman": offsets,     # untuk sitasi nomor halaman
            "n_kata": len(teks.split()),
            "teks": teks,
        } 
        out = CLEAN_DIR / f"{int(row['no_urut']):03d}.json"
        out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        
    print(f"{len(manifest)} perkara diekstrak ke {CLEAN_DIR}")
    print(f"Karakter mentah {total_raw:,} -> bersih {total_clean:,} "
          f"({1 - total_clean / total_raw:.0%} noise dibuang)")

if __name__ == "__main__":
    main()