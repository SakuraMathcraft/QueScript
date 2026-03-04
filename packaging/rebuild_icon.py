from pathlib import Path
from PIL import Image

ICON_PATH = Path(r"E:\QueScript\packaging\app_icon.ico")
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def rebuild_icon(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Icon not found: {path}")

    src = Image.open(path).convert("RGBA")
    w, h = src.size
    side = max(w, h)

    # Force square source so all sizes render correctly in Windows Explorer.
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(src, ((side - w) // 2, (side - h) // 2), src)
    canvas.save(path, format="ICO", sizes=SIZES)

    verify = Image.open(path)
    embedded = sorted(verify.info.get("sizes", []))
    print(f"Rebuilt: {path}")
    print(f"Embedded sizes: {embedded}")


if __name__ == "__main__":
    rebuild_icon(ICON_PATH)

