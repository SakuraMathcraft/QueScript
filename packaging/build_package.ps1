param(
    [switch]$BuildInstaller,
    [switch]$SkipBuild,
    [string]$LocalChromeZip = "E:\QueScript\chrome-win64.zip"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[build] $Message" -ForegroundColor Cyan
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$PlaywrightCache = Join-Path $RepoRoot "ms-playwright"
$LocalChromiumDir = Join-Path $PlaywrightCache "chrome-win64"
$LocalChromiumExe = Join-Path $LocalChromiumDir "chrome.exe"
$SpecPath = Join-Path $RepoRoot "packaging\quescript_gui.spec"
$DistDir = Join-Path $RepoRoot "dist\QueScriptSurvey"
$InstallerScript = Join-Path $RepoRoot "packaging\installer.iss"

Write-Step "Repo: $RepoRoot"
Write-Step "Python: $PythonExe"
Write-Step "Local Chrome zip: $LocalChromeZip"

if (-not (Test-Path $SpecPath)) {
    throw "Missing spec file: $SpecPath"
}

if ($SkipBuild) {
    Write-Step "SkipBuild enabled. Preflight checks complete."
    exit 0
}

Push-Location $RepoRoot
try {
    Write-Step "Installing/updating build tools"
    & $PythonExe -m pip install --upgrade pip pyinstaller | Out-Null

    # Make repo root discoverable inside PyInstaller spec execution context.
    $env:QUESCRIPT_REPO_ROOT = $RepoRoot

    if (-not (Test-Path $PlaywrightCache)) {
        New-Item -ItemType Directory -Path $PlaywrightCache | Out-Null
    }

    if (-not (Test-Path $LocalChromeZip)) {
        throw "Missing local browser package: $LocalChromeZip"
    }

    Write-Step "Preparing offline Chromium from local zip"
    if (Test-Path $LocalChromiumDir) {
        Remove-Item -Recurse -Force $LocalChromiumDir
    }
    Expand-Archive -Path $LocalChromeZip -DestinationPath $PlaywrightCache -Force

    if (-not (Test-Path $LocalChromiumExe)) {
        throw "Offline Chromium extraction failed, chrome.exe not found: $LocalChromiumExe"
    }

    # Expose browser executable path to app runtime and PyInstaller subprocess.
    $env:QUESCRIPT_CHROMIUM_EXECUTABLE = $LocalChromiumExe

    Write-Step "Running PyInstaller"
    & $PythonExe -m PyInstaller --noconfirm --clean $SpecPath

    if (-not (Test-Path (Join-Path $DistDir "QueScriptSurvey.exe"))) {
        throw "Build failed: executable not found in $DistDir"
    }

    Write-Step "Build output ready: $DistDir"

    if ($BuildInstaller) {
        if (-not (Test-Path $InstallerScript)) {
            throw "Missing installer script: $InstallerScript"
        }

        $iscc = Get-Command iscc -ErrorAction SilentlyContinue
        if (-not $iscc) {
            throw "Inno Setup compiler (iscc) not found in PATH. Install Inno Setup or run without -BuildInstaller."
        }

        Write-Step "Building installer with Inno Setup"
        & $iscc.Source $InstallerScript
    }
}
finally {
    Pop-Location
}

Write-Step "Done"
