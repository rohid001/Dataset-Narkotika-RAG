"""Path dan konfigurasi bersama untuk seluruh pipeline."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"              # 51 PDF asli dari Direktori Putusan MA
CLEAN_DIR = DATA_DIR / "clean"          # JSON teks bersih per perkara (Fase 1)
MANIFEST = DATA_DIR / "manifest.csv"    # peta nama file hash -> nomor perkara
METADATA_DB = DATA_DIR / "metadata.db"  # tabel perkara (Fase 2)
CHUNKS = DATA_DIR / "chunks.jsonl"      # chunk + metadata (Fase 3)
CHROMA_DIR = DATA_DIR / "chroma"        # vector store (Fase 5)
EVAL_DIR = ROOT / "eval"                # pertanyaan dan hasil evaluasi (Fase 4-6)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
