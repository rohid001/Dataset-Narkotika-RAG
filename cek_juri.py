"""Kenapa juri (Groq) membalas kosong untuk A079? Coba beberapa pengaturan."""
from groq import Groq

from src.config import GROQ_API_KEY
from src.eval_answers import PROMPT_JURI, SYSTEM_JURI, susun_sumber
from src.generate import GROQ_MODEL

# isi persis seperti di hasil_jawaban.csv untuk A079
hasil = {"rute": "agregat", "jawaban": "49 perkara.", "sumber": [],
         "sql": "SELECT COUNT(*) FROM perkara WHERE penasihat_hukum = 1", "hasil_sql": "COUNT(*)\n49"}
prompt = PROMPT_JURI.format(pertanyaan="Berapa perkara yang terdakwanya didampingi penasihat hukum?",
                            kunci="49 dari 51 perkara.", jawaban=hasil["jawaban"], sumber=susun_sumber(hasil))

client = Groq(api_key=GROQ_API_KEY)
for temperature, effort in [(0, "medium"), (0, "medium"), (0, "low"), (0.3, "medium")]:
    r = client.chat.completions.create(
        model=GROQ_MODEL, temperature=temperature, reasoning_effort=effort,
        messages=[{"role": "system", "content": SYSTEM_JURI}, {"role": "user", "content": prompt}],
    )
    c = r.choices[0]
    print(f"temperature={temperature} effort={effort:<6} | finish_reason={c.finish_reason} | "
          f"token keluar={r.usage.completion_tokens} | balasan={c.message.content!r}")