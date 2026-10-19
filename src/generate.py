"""Fase 6a: satu fungsi 'generate()' untuk memanggil LLM.

Provider utama Gemini; bila gagal (mis. kuota habis) dan GROQ_API_KEY terisi,
otomasi pindah ke Groq. Ganti provider cukup lewat file .env (LLM_PROVIDER=gemini / groq).

Coba: python -m src.generate
"""

import time
from src.config import GROQ_API_KEY, LLM_API_KEY, LLM_MODEL, LLM_PROVIDER

GROQ_MODEL = "openai/gpt-oss-20b"
GEMINI_HABIS = False                # True bila kuota HARIAN Gemini habis: sisa proses langsung memakai Groq
PROVIDER_TERAKHIR = ""              # provider yang menjawab panggilan terakhir (dicatat oleh eval_answers.py)

def panggil_gemini(prompt: str, system: str, temperature: float) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=LLM_API_KEY)
    resp = client.models.generate_content(
        model=LLM_MODEL or "gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system, 
            temperature=temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
    )
    return resp.text or ""

def panggil_groq(prompt: str, system: str, temperature: float, effort: str = "medium") -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature,
        reasoning_effort=effort,
    )
    return resp.choices[0].message.content or ""

def generate(prompt: str, system: str = "", temperature: float=0.1, coba: int = 5) -> str:
    """Kirim prompt ke LLM dan kembalikan teks jawabannya.
    
    - Gemini gagal + GROQ_API_KEY terisi -> percobaan berikutnya memakai Groq (tanpa menunggu).
    - Kuota harian Gemini habis -> Gemini dilewati untuk sisa proses.
    - Selain itu (mis. batas token per menit Groq) -> tunggu 10, 20, 30, ... detik lalu coba lagi.
    """
    global GEMINI_HABIS, PROVIDER_TERAKHIR
    pakai_groq = LLM_PROVIDER == "groq" or GEMINI_HABIS
    effort = "medium"
    for i in range(coba):
        nama = "groq" if pakai_groq else "gemini"
        try:
            if pakai_groq:
                teks = panggil_groq(prompt, system, temperature, effort)
            else:
                teks = panggil_gemini(prompt, system, temperature)
            if not teks.strip():
                # gpt-oss kadang "berpikir" sampai batas token tanpa sempat menjawab (finish_reason=length)
                # percobaan berikutnya memakai reasoning_effort="low" supaya bagian berpikirnya lebih pendek
                effort = "low"
                raise ValueError("balasan kosong dari LLM")
            PROVIDER_TERAKHIR = nama
            return teks
        except Exception as e:
            print(f"    [{nama}] gagal: {e.__class__.__name__}: {str(e)[:120]}")
            if not pakai_groq and GROQ_API_KEY:
                if "PerDay" in str(e):
                    GEMINI_HABIS = True
                    print(" kuota harian Gemini habis -> sisa proses memakai Groq")
                else:
                    print(" pindah ke Groq")
                pakai_groq = True
                continue
            time.sleep(10 * (i + 1))
    raise RuntimeError("LLM tidak bisa dihubungi. Cek API key dan kuota di file .env")

if __name__=="__main__":
    print("Provider:", LLM_PROVIDER)
    print(generate("Jawab dengan satu kalimat: apa itu putusan pengadilan?"))