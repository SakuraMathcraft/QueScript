from pathlib import Path
import json
import pandas as pd

base = Path(__file__).resolve().parent
for name in ["survey_data_collected.csv", "path_log.csv", "config.json"]:
    p = base / name
    print(f"--- {name} exists={p.exists()} size={p.stat().st_size if p.exists() else 0}")

csv_path = base / "survey_data_collected.csv"
if csv_path.exists() and csv_path.stat().st_size > 0:
    df = pd.read_csv(csv_path)
    print("rows, cols =", df.shape)
    print("columns=", list(df.columns))
    nn = df.notna().mean().sort_values(ascending=False)
    print("non-null ratio top 20:")
    print(nn.head(20).to_string())
    if "Q24" in df.columns:
        print("Q24 non-null ratio=", df["Q24"].notna().mean())
        print("Q24 sample values=", df["Q24"].dropna().head(3).tolist())

pl = base / "path_log.csv"
if pl.exists() and pl.stat().st_size > 0:
    pldf = pd.read_csv(pl)
    print("path_log rows=", len(pldf), "cols=", list(pldf.columns))
    if "jump_reasons" in pldf.columns:
        jump_count = (pldf["jump_reasons"].astype(str).str.lower() != "none").sum()
        print("jump count=", int(jump_count))
    print(pldf.head(3).to_string(index=False))

cfg = base / "config.json"
if cfg.exists() and cfg.stat().st_size > 0:
    data = json.loads(cfg.read_text(encoding="utf-8"))
    print("config keys=", sorted(data.keys()))
    print("config run_id=", data.get("run_id"), "seed=", data.get("seed"))

