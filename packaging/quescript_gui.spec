# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all

env_root = os.environ.get("QUESCRIPT_REPO_ROOT", "").strip()
if env_root:
    root_candidate = Path(env_root)
else:
    root_candidate = Path.cwd()

if (root_candidate / "mock_survey" / "gui_launcher.py").exists():
    project_root = root_candidate
elif (root_candidate.parent / "mock_survey" / "gui_launcher.py").exists():
    project_root = root_candidate.parent
else:
    raise FileNotFoundError(
        "Cannot resolve project root. Set QUESCRIPT_REPO_ROOT or run build from repository root."
    )

entry_script = project_root / "mock_survey" / "gui_launcher.py"

if not entry_script.exists():
    raise FileNotFoundError(f"Entry script not found: {entry_script}")

datas = [
    (str(project_root / "mock_survey"), "mock_survey"),
]

playwright_cache = project_root / "ms-playwright"
if playwright_cache.exists():
    datas.append((str(playwright_cache), "ms-playwright"))

binaries = []
hiddenimports = []

for pkg in ["ttkbootstrap", "playwright", "numpy", "pandas", "scipy"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

runtime_hooks = [str(project_root / "packaging" / "playwright_runtime_hook.py")]
icon_file = project_root / "packaging" / "app_icon.ico"

block_cipher = None

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root), str(project_root / "mock_survey")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QueScriptSurvey",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_file) if icon_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="QueScriptSurvey",
)
