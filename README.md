# QueScript (v1.0)

QueScript is a local survey simulation toolkit with a GUI, automatic questionnaire generation, batch response simulation, and data quality analysis (reliability/validity/discrimination/EFA).

## Features

- Convert plain-text questionnaire content into HTML survey pages
- Run batch smart simulation with configurable sample size and response bias
- Enforce skip logic paths and output audit artifacts (`config.json`, `path_log.csv`)
- Generate analysis report including:
  - Cronbach's alpha
  - KMO + Bartlett test
  - Item-level discrimination (CR)
  - CITC / alpha-if-deleted diagnostics
  - EFA factor outputs
- Offline packaging support for Windows (PyInstaller + Inno Setup)

## Quick Start

```powershell
cd E:\QueScript
.\.venv\Scripts\activate
python mock_survey\gui_launcher.py
```

## Dependencies

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Packaging (Windows, offline)

```powershell
cd E:\QueScript
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -LocalChromeZip "E:\QueScript\chrome-win64.zip"
```

## Project Structure

- `mock_survey/`: simulation core, GUI launcher, survey generator, analysis
- `packaging/`: build scripts and installer configuration
- `requirements.txt`: Python dependencies

## License

MIT License

