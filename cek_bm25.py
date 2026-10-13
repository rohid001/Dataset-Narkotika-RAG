import hashlib
import json

from src.eval_retrieval import benar
from src.retrieve import cari

for f in ["data/chunks.jsonl", "eval/questions.jsonl"]:
    print(f, hashlib.md5(open(f, encoding="utf-8").read().encode()).hexdigest())

soal = [json.loads(b) for b in open("eval/questions.jsonl", encoding="utf-8")]
hasil = []
for q in soal:
    if not q["perkara"]:
        continue
    ids = cari(q["pertanyaan"], k=5, mode="bm25", pakai_filter=False)
    pos = next((i for i, c in enumerate(ids, 1) if benar(c, q)), "-")
    hasil.append(f"{q['id']}:{pos}")
print(" ".join(hasil))