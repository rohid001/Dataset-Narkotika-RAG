import pandas as pd

df = pd.read_csv("eval/hasil_jawaban.csv")
gagal = df.jawaban.fillna("").str.strip().eq("") | df.alasan.fillna("").str.startswith("juri tidak membalas JSON")
print("dinilai ulang:", df[gagal].id.tolist())
df[~gagal].to_csv("eval/hasil_jawaban.csv", index=False)