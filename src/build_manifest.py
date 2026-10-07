"""Fase 0: buat data/manifest.csv yang memetakan nama file PDF (hash) ke nomor perkara.

Jalankan:  python -m src.build_manifest
"""
import csv
import hashlib
import re

import pymupdf

from src.config import MANIFEST, RAW_DIR

NOMOR_RE = re.compile(r"Nomor\s+(\d+/Pid\.[A-Za-z\.\-]+/\d{4}/PN\s*Rap)")


def main() -> None:
    rows = []
    for pdf in sorted(RAW_DIR.glob("*.pdf")):
        with pymupdf.open(pdf) as doc:
            first = doc[0].get_text()
            n_pages = doc.page_count
        m = NOMOR_RE.search(first)
        if not m:
            raise ValueError(f"Nomor perkara tidak ditemukan di {pdf.name}")
        nomor = re.sub(r"\s+", " ", m.group(1))
        rows.append({
            "nomor": nomor,
            "no_urut": int(nomor.split("/")[0]),
            "tahun": int(nomor.split("/")[2]),
            "file": pdf.name,
            "halaman": n_pages,
            "ukuran_kb": round(pdf.stat().st_size / 1024, 1),
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        })

    nomors = [r["nomor"] for r in rows]
    dup = {n for n in nomors if nomors.count(n) > 1}
    if dup:
        raise ValueError(f"Nomor perkara duplikat: {sorted(dup)}")

    rows.sort(key=lambda r: r["no_urut"])
    with open(MANIFEST, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} perkara, {sum(r['halaman'] for r in rows)} halaman -> {MANIFEST}")


if __name__ == "__main__":
    main()