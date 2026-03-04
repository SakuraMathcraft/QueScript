from pathlib import Path


def top(path: Path, n: int = 15) -> None:
    rows = []
    for p in path.iterdir():
        if p.is_dir():
            s = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        elif p.is_file():
            s = p.stat().st_size
        else:
            continue
        rows.append((s, p.name))
    rows.sort(reverse=True)
    total = sum(s for s, _ in rows)
    print(f"[{path}] total={total / 1024 / 1024:.2f} MB")
    for s, name in rows[:n]:
        print(f"  {name}: {s / 1024 / 1024:.2f} MB")


root = Path(r"E:\QueScript\dist\QueScriptSurvey\_internal")
for name in ["ms-playwright", "playwright", "scipy", "pandas", "numpy"]:
    p = root / name
    if p.exists():
        top(p)
        print()

