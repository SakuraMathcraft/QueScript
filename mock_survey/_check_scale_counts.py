import re
from pathlib import Path

import pandas as pd

html = Path(r"E:\QueScript\mock_survey\index.html").read_text(encoding="utf-8", errors="replace")
scale_qids = re.findall(r'id="q(\d+)"[^>]*data-type="scale_radio"', html)
matrix_qids = re.findall(r'id="q(\d+)"[^>]*data-type="matrix"', html)
print("scale_radio_count", len(scale_qids), scale_qids)
print("matrix_count", len(matrix_qids), matrix_qids)

df = pd.read_csv(r"E:\QueScript\mock_survey\survey_data_collected.csv")
qcols = [c for c in df.columns if c.startswith("Q")]

expanded = []
for c in qcols:
    s = df[c].astype(str)
    if s.str.contains("|", regex=False).mean() >= 0.2:
        t = s.str.split("|", expand=True, regex=False)
        t.columns = [f"{c}_r{i+1}" for i in range(t.shape[1])]
        expanded.append(t)
    else:
        expanded.append(pd.DataFrame({c: df[c]}))

num = pd.concat(expanded, axis=1)
num = num.replace({"": None, "None": None, "nan": None}).apply(pd.to_numeric, errors="coerce")
ratio = num.notna().mean()
common = ratio[ratio >= 0.999].index.tolist()
print("common_count", len(common))
print("common_items", common)
print("top_answer_ratio", ratio.sort_values(ascending=False).head(30).to_dict())

