"""Fase 0: cek bahwa API key dan library sudah siap dipakai.
Jalankan: python -m src.cek_koneksi
"""

from src.config import GROQ_API_KEY, LLM_API_KEY, LLM_MODEL

def cek_gemini()-> str:
    from google import genai
    client = genai.Client(api_key=LLM_API_KEY)
    resp = client.models.generate_content(
        model=LLM_MODEL,
        contents="Jawab dengan satu kalimat: apa itu putusan pengadilan",
    )
    return resp.text

def cek_groq() -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Jawab satu kata: siap?"}],
    )
    return resp.choices[0].message.content

def cek_embedding() -> str:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    vektor = model.encode(["tes"])
    return f"bentuk vektor {vektor.shape}"

if __name__ == "__main__":
    for nama, fungsi in [("Gemini", cek_gemini), ("Groq", cek_groq), ("Embedding", cek_embedding)]:
        try:
            print(f"[OK]    {nama}: {fungsi()}")
        except Exception as e:
            print(f"[GAGAL] {nama}: {e.__class__.__name__}:{str(e)[:150]}")