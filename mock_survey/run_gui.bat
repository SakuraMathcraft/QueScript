@echo off
cd /d "%~dp0"
echo Starting Survey GUI...
if exist "..\.venv\Scripts\python.exe" (
    ..\.venv\Scripts\python.exe gui_launcher.py
) else (
    python gui_launcher.py
)

echo.
echo GUI closed. Press Enter to exit...
set /p _exit_prompt=
