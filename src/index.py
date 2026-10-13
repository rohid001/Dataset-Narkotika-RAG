"""Fase 5a: bangun dua indeks dari data/chunks.jsonl.

- Indeks BM25: mencari berdasarkan kata yang persis sama (nomor perkara, nama, lokasi).
- Indeks vektor (Chroma): mencari berdasarkan kemiripan makna.

Jalankan: python -m src.index
Ganti model embeddin lewat EMBEDDING_MODEL di file .env.
"""
import json
import pickle
import re
import time

from src.config import CHROMA_DIR, CHUNKS, DATA_DIR, EMBEDDING_MODEL

BM25_PATH = DATA_DIR / "bm25.pkl"
COLLECTION = "putusan"

#------------------------------------------------------------------Tahap A: persiapan teks dan indeks BM25

def load_chunks() -> list[dict]:
    with open(CHUNKS, encoding="utf-8") as fh:
        return [json.loads(baris) for baris in fh]
    
def tokenisasi(teks: str) -> list[str]:
    """Huruf kecil, pisah per kata. Nomor seperti '268/Pid.Sus/2023' menjadi token '268', 'pid', 'sus', '2023'."""
    return re.findall(r"[a-z0-9]+", teks.lower())

def teks_untuk_embedding(chunk: dict) -> str:
    """Tambahkan nomor perkara dan nama bagian di depan isi chunk agar pencarian tahu asal potongannya."""
    return f"Perkara {chunk['nomor']} | bagian {chunk['bagian']}\n{chunk['teks']}"

def build_bm25(chunks: list[dict]) -> None:
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi([tokenisasi(teks_untuk_embedding(c)) for c in chunks])
    with open(BM25_PATH, "wb") as fh:
        pickle.dump({"bm25": bm25, "ids": [c["id"] for c in chunks]}, fh)
    print(f"BM25: {len(chunks)} chunk -> {BM25_PATH.name}")

#------------------------------------------------------------------Tahap B: indeks vektor Chroma

def build_chroma(chunks: list[dict]) -> None:
    import chromadb
    from src.embedding import Embedder
    
    mulai = time.time()
    vektor = Embedder().encode_dokumen([teks_untuk_embedding(c) for c in chunks])
    print(f"Embedding {len(chunks)} chunk dengan {EMBEDDING_MODEL} selesai dalam {time.time() - mulai:.0f} detik")
    
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION)    # bangun ulang dari nol setiap kali
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine", "model":EMBEDDING_MODEL})
    
    metadata_keys = ["nomor", "no_urut", "bagian", "pasal", "jenis_narkotika", "vonis_bulan", 
                     "hakim_ketua"]
    for i in range(0, len(chunks), 500):    # Chorma membatasi jumlah data per sekali tambah
        batch = chunks[i:i + 500]
        col.add(
            ids=[c["id"] for c in batch],
            documents=[c["teks"] for c in batch],
            embeddings=[v.tolist() for v in vektor[i:i + 500]],
            metadatas=[{k: c[k] for k in metadata_keys} for c in batch],
        )
    print(f"Chroma: {col.count()} chunk -> {CHROMA_DIR}")
    
def main() -> None:
    chunks = load_chunks()
    build_bm25(chunks)
    build_chroma(chunks)

if __name__ == "__main__":
    main()