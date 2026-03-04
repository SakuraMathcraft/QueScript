import os
import sys
from pathlib import Path


def _safe_set_playwright_path() -> None:
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return

    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    candidates = [
        Path(sys.executable).resolve().parent / "ms-playwright",
        base_dir / "ms-playwright",
    ]
    for path in candidates:
        if path.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
            return


def _safe_set_chromium_executable() -> None:
    if os.environ.get("QUESCRIPT_CHROMIUM_EXECUTABLE"):
        return

    exe_name = "chrome.exe" if os.name == "nt" else "chrome"
    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    candidates = [
        Path(sys.executable).resolve().parent / "ms-playwright" / "chrome-win64" / exe_name,
        base_dir / "ms-playwright" / "chrome-win64" / exe_name,
        Path(sys.executable).resolve().parent / "chrome-win64" / exe_name,
    ]
    for path in candidates:
        if path.exists():
            os.environ["QUESCRIPT_CHROMIUM_EXECUTABLE"] = str(path)
            return


def _safe_set_writable_cwd() -> None:
    # Installed apps may run under Program Files (not writable). Use LocalAppData.
    if not getattr(sys, "frozen", False):
        return

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return

    work_dir = Path(local_app_data) / "QueScriptSurvey"
    (work_dir / "mock_survey").mkdir(parents=True, exist_ok=True)
    os.chdir(work_dir)


_safe_set_playwright_path()
_safe_set_chromium_executable()
_safe_set_writable_cwd()
