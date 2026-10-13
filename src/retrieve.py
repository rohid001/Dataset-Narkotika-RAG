"""Fase 5b: cari chunk yang relevan untuk sebuah pertanyaan.

Tiga cara mencari, dibandingkan di eval_retrieval.py
- vektor    : kemiripan makna (Chroma)
- bm25      : kecocokan kata (BM25)
- hibrida   : gabungan keudanya dengan Reciporcal Rank Fusion (RRF)

Bila pertanyaan menyebut perkara (mis. "perkara 268"), pencarian dibatasi ke perkara itu.

Coba: python -m src.retrieve "bagaimana kronologi penangkapan di perkara 268?"
"""

import pickle
import re
import sys
from functools import lru_cache

from src.config import CHROMA_DIR, EMBEDDING_MODEL
from src.index import BM25_PATH, COLLECTION, load_chunks, tokenisasi

#-------------------------------------------------------------------Tahap A: nomor perkara dan RRF

RRF_K = 60  # konstanta standar RRF; makin besar, makin rata bobot antar-peringkat

def nomor_disebut(pertanyaan: str) -> list[int]:
    """Semua nomor perkara yang disebut.
    
    'perkara 267/Pid.Sus/2023/PN Rap' -> [268]; 'perkara 417, 418, dan 419' -> [417, 418, 419]
    """
    # 1) nomor lengkap: "268/Pid.Sus/2023/PN Rap"
    nomor = [int(n) for n in re.findall(r"\b(\d{2,4})/Pid", pertanyaan, re.I)]
    # 2) nomor penek setelah kata "perkara"/"nomor": "perkara 417, 418, dan 419"
    pola = r"(?:perkara|nomor)\s+((?:\d{2,4}(?:\s*,\s*(?:dan\s+)?|\s+dan\s+|\s*&\s*)?)+)"
    for m in re.finditer(pola, pertanyaan, re.I):
        nomor += [int(n) for n in re.findall(r"\d{2,4}", m.group(1)) if not 2000 <= int(n) <= 2099]
    return list(dict.fromkeys(nomor))   # buang duplikat, urutan tetap

def gabung_rrf(*daftar_peringkat: list[str], k: int = 5) -> list[str]:
    """Reciprocal Rank Fusion: skor = jumlah 1 / (RRF_K + peringkat) dari setiap daftar."""
    skor = {}
    for daftar in daftar_peringkat:
        for peringkat, cid in enumerate(daftar, 1):
            skor[cid] = skor.get(cid, 0) + 1 / (RRF_K + peringkat)
    return sorted(skor, key=skor.get, reverse=True)[:k]

#-------------------------------------------------------------------Tahap B: pencarian BM25 dan vektor

@lru_cache(maxsize=1)
def muat_chunks() -> dict[str, dict]:
    """Semua chunk, diakses lewat id-nya: {'268-021': {...}, ...}."""
    return {c["id"]: c for c in load_chunks()}

@lru_cache(maxsize=1)
def muat_bm25()-> dict:
    with open(BM25_PATH, "rb") as fh:
        return pickle.load(fh)
    
@lru_cache(maxsize=1)
def muat_vektor():
    """Model embedding + koleksi Chroma. Dimuat sekali saja karena model besar lambar dimuat."""
    import chromadb
    from src.embedding import Embedder
    col = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(COLLECTION)
    if col.metadata.get("model") != EMBEDDING_MODEL:
        raise RuntimeError(f"Indeks dibuat dengan {col.metadata.get('model')}, tetapi .env memakai "
                           f"{EMBEDDING_MODEL}. Jalankan ulang: python -m src.index")
    return Embedder(), col

def cari_bm25(pertanyaan: str, k: int = 20, no_urut: int | None=None)-> list[str]:
    bm = muat_bm25()
    skor = bm["bm25"].get_scores(tokenisasi(pertanyaan))
    urut = sorted(range(len(skor)), key=lambda i: skor[i], reverse=True) # Indeks chunk, skor tertinggi dulu
    ids = [bm["ids"][i] for i in urut]
    if no_urut:
        chunks = muat_chunks()
        ids = [cid for cid in ids if chunks[cid]["no_urut"] == no_urut]
    return ids[:k]

def cari_vektor(pertanyaan: str, k: int=20, no_urut: int | None = None) -> list[str]:
    model, col = muat_vektor()
    q = model.encode_query(pertanyaan).tolist()
    where = {"no_urut": no_urut} if no_urut else None   # filter metadata Chroma
    hasil = col.query(query_embeddings=[q], n_results=k, where=where)
    return hasil["ids"][0]

#-------------------------------------------------------------------Tahap C: satu pintu perncarian

def cari_dengan_model(pertanyaan: str, k: int, mode: str, no_urut: int | None) -> list[str]:
    if mode == "vektor":
        return cari_vektor(pertanyaan, k, no_urut)
    if mode == "bm25":
        return cari_bm25(pertanyaan, k, no_urut)
    return gabung_rrf(cari_vektor(pertanyaan, 20, no_urut), cari_bm25(pertanyaan, 20, no_urut), k=k)

def cari(pertanyaan: str, k: int=5, mode: str="hibrida", pakai_filter:bool = True) -> list[dict]:
    """Kembalikan k chunk teratas (dict lengkap dengan teks dan metadata).
    
    Bila pertanyaan menyebut beberapa nomor perkara, setiap perkara mendapat jatah chunk sendiri."""
    chunks = muat_chunks()
    nomor = []
    if pakai_filter:
        ada = {c["no_urut"] for c in chunks.values()}
        nomor = [n for n in nomor_disebut(pertanyaan) if n in ada] # abaikan nomor yang tidak ada di dataset
    
    if not nomor:
        ids = cari_dengan_model(pertanyaan, k, mode, None)
    else:
        jatah = max(2, k // len(nomor))
        ids = []
        for n in nomor:
            ids += cari_dengan_model(pertanyaan, jatah, mode, n)
    return [chunks[cid] for cid in ids]

if __name__ == "__main__":
    tanya = " ".join(sys.argv[1:]) or "Bagaimana kronologi penangkapan dalam perkara 268?"
    for c in cari(tanya):
        print(f"[{c['id']}] {c['nomor']} | {c['bagian']}\n {c['teks'][:200]}...\n")
