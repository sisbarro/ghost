[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallerDir = Join-Path $ProjectRoot "installer"

Push-Location $ProjectRoot
try {
    Write-Host "[1/4] Installing build dependencies..."
    py -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt

    Write-Host "[2/4] Building the standalone application..."
    py -m PyInstaller --clean --noconfirm GhostMail.spec

    Write-Host "[3/4] Locating Inno Setup..."
    $IsccCandidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }

    $Iscc = $IsccCandidates | Select-Object -First 1
    if (-not $Iscc) {
        $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $Winget) {
            throw "Inno Setup 6 is required. Install it from https://jrsoftware.org/isdl.php and run this script again."
        }
        Write-Host "Inno Setup is missing; installing it with winget..."
        & $Winget.Source install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "winget could not install Inno Setup (exit code $LASTEXITCODE)."
        }
        $Iscc = @(
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $Iscc) {
        throw "Inno Setup installed, but ISCC.exe could not be found."
    }

    Write-Host "[4/4] Building the installer..."
    & $Iscc (Join-Path $InstallerDir "GhostMail.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }

    $SetupPath = Join-Path $InstallerDir "output\GhostMail-Setup.exe"
    Write-Host ""
    Write-Host "Installer ready: $SetupPath" -ForegroundColor Green
}
finally {
    Pop-Location
}