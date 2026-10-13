import pickle
from collections import Counter
from pathlib import Path

p = Path("data/cache_gemini.pkl")
with open(p, "rb") as fh:
    cache = pickle.load(fh)
print("Sebelum:", dict(Counter(len(v) for v in cache.values())))
for k, v in cache.items():
    if len(v) == 769:
        cache[k] = v[:768]          # buang 1 angka terakhir
print("Sesudah:", dict(Counter(len(v) for v in cache.values())))
with open(p, "wb") as fh:
    pickle.dump(cache, fh)