"""Cari tahu kenapa Groq membalas kosong untuk satu pertanyaan (default: A058)."""
import json
import sys

from groq import Groq

from src.config import GROQ_API_KEY, RETRIEVAL_MODE
from src.generate import GROQ_MODEL
from src.rag import SYSTEM_RAG, cari, fakta_terstruktur, nomor_dari_nama, nomor_disebut, susun_konteks

id_soal = sys.argv[1] if len(sys.argv) > 1 else "A058"
soal = [json.loads(b) for b in open("eval/questions.jsonl", encoding="utf-8")]
q = next(s for s in soal if s["id"] == id_soal)
print(id_soal, ":", q["pertanyaan"])

# prompt disusun persis seperti jawab() di rag.py
nomor = nomor_disebut(q["pertanyaan"]) or nomor_dari_nama(q["pertanyaan"])
fakta = "\n\n".join(f for f in (fakta_terstruktur(n) for n in nomor) if f)
prompt = f"FAKTA TERSTRUKTUR (dari tabel metadata):\n{fakta}\n\n" if fakta else ""
prompt += f"KONTEKS:\n{susun_konteks(cari(q['pertanyaan'], k=6, mode=RETRIEVAL_MODE))}\n\nPERTANYAAN: {q['pertanyaan']}\n\nJAWABAN:"

client = Groq(api_key=GROQ_API_KEY)
for effort in ["medium", "low"]:
    r = client.chat.completions.create(
        model=GROQ_MODEL, temperature=0.1, reasoning_effort=effort,
        messages=[{"role": "system", "content": SYSTEM_RAG}, {"role": "user", "content": prompt}],
    )
    c = r.choices[0]
    print(f"\nreasoning_effort={effort} | finish_reason={c.finish_reason} | "
          f"token masuk={r.usage.prompt_tokens} | token keluar={r.usage.completion_tokens} | "
          f"panjang jawaban={len(c.message.content or '')}")
    print((c.message.content or "(kosong)")[:300])