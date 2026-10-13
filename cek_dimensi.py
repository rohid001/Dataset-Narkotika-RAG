import hashlib
import pickle

import numpy as np
from google import genai
from google.genai import types

from src.config import LLM_API_KEY
from src.index import load_chunks, teks_untuk_embedding

with open("data/cache_gemini.pkl", "rb") as fh:
    cache = pickle.load(fh)
teks = [teks_untuk_embedding(c) for c in load_chunks()[:3]]
client = genai.Client(api_key=LLM_API_KEY)
resp = client.models.embed_content(
    model="gemini-embedding-001",
    contents=teks,
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768),
)
for t, emb in zip(teks, resp.embeddings):
    kunci = hashlib.md5(f"gemini-embedding-001|RETRIEVAL_DOCUMENT|{t}".encode("utf-8")).hexdigest()
    a, b = cache[kunci], np.array(emb.values)
    print(f"cosine = {a @ b / (np.linalg.norm(a) * np.linalg.norm(b)):.6f}")