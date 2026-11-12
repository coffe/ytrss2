# Windows build for YTRSS 2.0 (PyInstaller cannot cross-compile; run this on Windows)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting build process for YTRSS 2.0 (Windows)..." -ForegroundColor Cyan

# Fresh start: clean old artifacts and venv
foreach ($d in "dist", "build", "bin", ".venv") {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
}
if (Test-Path "ytrss.spec") { Remove-Item -Force "ytrss.spec" }

Write-Host "Creating fresh virtual environment..." -ForegroundColor Cyan
python -m venv .venv
$py = ".venv\Scripts\python.exe"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $py -m pip install -r requirements.txt --quiet
& $py -m pip install pyinstaller==6.22.3 --quiet

Write-Host "Compiling binary..." -ForegroundColor Yellow
# Windows uses ';' as the --add-data separator
& $py -m PyInstaller --onefile --name ytrss --add-data "KEYS.md;." --clean --log-level=WARN ytrss.py

if (Test-Path "dist\ytrss.exe") {
    New-Item -ItemType Directory -Force -Path "bin" | Out-Null
    Copy-Item -Path "dist\ytrss.exe" -Destination "bin\"
    Write-Host "Build complete: bin\ytrss.exe" -ForegroundColor Green
    Write-Host "Needs mpv and yt-dlp on PATH at runtime."
} else {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
