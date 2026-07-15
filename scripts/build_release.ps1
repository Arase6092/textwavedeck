param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment was not found: $Python"
}

$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$ReleaseRoot = Join-Path $DistRoot "release"
$BundleName = "WaveDeck-v$Version-windows-x64"
$BundleRoot = Join-Path $ReleaseRoot $BundleName
$AssetPath = Join-Path $ReleaseRoot "$BundleName.zip"
$SpecPath = Join-Path $ProjectRoot "WaveDeck.spec"

& $Python -m pip install pyinstaller | Out-Host

if (Test-Path $BundleRoot) {
    Remove-Item -LiteralPath $BundleRoot -Recurse -Force
}
if (Test-Path $AssetPath) {
    Remove-Item -LiteralPath $AssetPath -Force
}

& $Python -m PyInstaller --noconfirm --clean $SpecPath | Out-Host

$PyInstallerDist = Join-Path $DistRoot "WaveDeck"
if (-not (Test-Path (Join-Path $PyInstallerDist "WaveDeck.exe"))) {
    throw "PyInstaller did not produce WaveDeck.exe"
}

New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
Copy-Item -LiteralPath $PyInstallerDist -Destination $BundleRoot -Recurse

$LaunchCmd = @'
@echo off
setlocal
cd /d "%~dp0"
start "" "WaveDeck.exe"
'@
Set-Content -LiteralPath (Join-Path $BundleRoot "Launch-WaveDeck.cmd") -Value $LaunchCmd -Encoding ascii

$Readme = @"
WaveDeck v$Version Windows Package

Requirements
- Windows 10 or Windows 11
- Microsoft PowerPoint 2016 or later

How to launch
1. Double-click WaveDeck.exe
2. Or run Launch-WaveDeck.cmd

Notes
- This package does not install PowerPoint for you.
- Slide cache and logs are written under %LOCALAPPDATA%\GesturePPT\
"@
Set-Content -LiteralPath (Join-Path $BundleRoot "README-QuickStart.txt") -Value $Readme -Encoding utf8

Compress-Archive -Path $BundleRoot -DestinationPath $AssetPath -Force

Write-Host "PACKAGE_OK $AssetPath"
