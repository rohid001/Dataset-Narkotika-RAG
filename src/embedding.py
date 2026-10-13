"""Fase 5: satu antarmuka untuk dua jeni model embedding.

- Model lokal (sentence-transformers): BAAI/bge-m3, intfloat/multilingual-e5-small, ...
Butuh Pytorch. Cocok untuk eksperimen di laptop atau Colab.
- Gemini Embedding API: gemini-embedding-001. Tanpa Pytorch, cocok untuk demo di
Streamlit Community Cloud (RAM terbatas 2,7 GB). Memakai API key Gemini yang sama.

Catatan: gemini-embedding-2 menggabungkan banyak teks dalam satu request menjadi SATU
embedding, jadi untuk embedding per chunk dipakai gemini-embedding-001.

Coba: python -m src.embedding
"""

import hashlib
import pickle
import time
import numpy as np

from src.config import EMBEDDING_MODEL, LLM_API_KEY, DATA_DIR

# Kuota gratis gemini-embedding-001 (per-project): 100 request/menit, 30.000 token/menit, 1.000 request/hari.
# Satu chunk sekitar 500 token, jadi 20 chunk per-request (~10.000 token) dnegan jeda 30 detik
# menjaga pemakaian di bawah 30.000 token/menit. Embedding 1.827 chunk butuh sekitar 45 menit.


UKURAN_BATCH_GEMINI = 20
JEDA_GEMINI = 30    # detik antar-request saat embedding banyak dokumen
MAKS_COBA = 10      # berapa kali mencoba ulang saat kena batas kuota (error 429)
CACHE_GEMINI = DATA_DIR / "cache_gemini.pkl"    # vektor yang sudah didapat; proses yang terhenti lanjut dari sini


class Embedder:
    """Ubah teks menjadi vektor, dengan model lokal atau Gemini sesuai EMBEDDING_MODEL."""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self.pakai_gemini = model_name.startswith("gemini-embedding")
        if self.pakai_gemini:
            from google import genai
            self.client = genai.Client(api_key=LLM_API_KEY)
        else:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name) # diunduh otomatis saat pertama kali
        
        # family model E5 dilatih dengan awalan "passage: " untuk dokumen dan "query: " untuk pertanyaan
        self.e5 = "e5" in model_name.lower()
        
    def encode_gemini(self, teks: list[str], task_type: str) -> np.ndarray:
        from google.genai import types
        
        # 1) muat cache: teks yang sudah pernah di-embed tidak dikirm lagi
        cache = {}
        if CACHE_GEMINI.exists():
            with open(CACHE_GEMINI, "rb") as fh:
                cache = pickle.load(fh)
        kunci = [hashlib.md5(f"{self.model_name}|{task_type}|{t}".encode("utf-8")).hexdigest() for t in teks]
        belum = [i for i, k in enumerate(kunci) if k not in cache]
        n_batch = -(-len(belum) // UKURAN_BATCH_GEMINI) # pembagian dibulatkan ke atas
        if len(teks) > 1:
            print(f"    Gemini: {len(teks) - len(belum)} teks dari cache, {len(belum)} teks dikirim ({n_batch} request)")
        
        # 2) kirim yang belum ada, per batch; simpan cache setelah setiap batch berhasil
        for nomor, i in enumerate(range(0, len(belum), UKURAN_BATCH_GEMINI), 1):
            idx = belum[i:i + UKURAN_BATCH_GEMINI]
            for coba in range(1, MAKS_COBA + 1):
                try:
                    resp = self.client.models.embed_content(
                        model=self.model_name,
                        contents=[teks[j] for j in idx],
                        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=768),
                    )
                    break
                except Exception as e:
                    if "PerDay" in str(e):      # kuota harian habis: menunggu beberapa menit tidak membantu
                        raise RuntimeError("Kuota harian Gemini (1.000 teks) habis. Progres sudah tersimpan di cache; "
                                           "jalankan ulang perintah yang sama setelah kuota direset "
                                           "(lihat 'Please retry in ...' di atas).") from e
                    kena_kuota = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                    if not kena_kuota or coba == MAKS_COBA:
                        raise       # errpr lain (mis. API key salah) langsung dihentikan
                    print(f"    batch {nomor}/{n_batch}: kuota per menit habis, tunggu 60 detik (percobaan {coba}/{MAKS_COBA})")
                    time.sleep(60)
            for j, emb in zip(idx, resp.embeddings):
                cache[kunci[j]] = np.array(emb.values, dtype=np.float32)
            with open(CACHE_GEMINI, "wb") as fh:
                pickle.dump(cache, fh)
            if n_batch > 1:
                print(f"    batch{nomor}/{n_batch} selesai")
                if nomor < n_batch:
                    time.sleep(JEDA_GEMINI)     # jaga di bawah batas token per menit
        
        # 3) susun hasil sesuai urutan teks, lalu normalkan (dimensi < 3072 perlu dinormalkan sendiri)
        v = np.array([cache[k] for k in kunci], dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)
        
    
    def encode_dokumen(self, teks: list[str]) -> np.ndarray:
        """Banyak teks (chunk) -> matriks (jumlah teks, dimensi)."""
        if self.pakai_gemini:
            return self.encode_gemini(teks, "RETRIEVAL_DOCUMENT")
        awalan = "passage: " if self.e5 else ""
        return self.model.encode([awalan + t for t in teks], batch_size=16,
                                 show_progress_bar=True, normalize_embeddings=True)
        
    def encode_query(self, teks: str) -> np.ndarray:
        """Satu pertanyaan -> satu vektor (dimensi,)."""
        if self.pakai_gemini:
            return self.encode_gemini([teks], "RETRIEVAL_QUERY")[0]
        awalan = "query: " if self.e5 else ""
        return self.model.encode([awalan + teks], normalize_embeddings=True)[0]
    
if __name__ == "__main__":
    model = Embedder()
    dokumen = [
        "Saksi melakukan patroli lalu mengamankan terdakwa yang membawa sabu di depan loket taksi.",
        "Majelis hakim menjatuhkan pidana penjara selama 4 tahun 6 bulan kepada terdakwa.",
        "Keadaan yang meringankan: terdakwa bersikap sopan dan mengakui perbuatannya.",
    ]
    vd = model.encode_dokumen(dokumen)
    vq = model.encode_query("Bagaimana penangkapan terdakwa?")
    print("Model    :", EMBEDDING_MODEL)
    print("Dokumen  :", vd.shape, "| query:", vq.shape)
    for teks, skor in zip(dokumen, vd @ vq):    # vektor sudah dinormalkan: perkalian titik = cosine
        print(f"    {skor:.3f}  {teks[:60]}")