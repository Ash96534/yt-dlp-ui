# Build script for Windows - creates NSIS installer
# Requires: pip install pyinstaller nsis
# Run in PowerShell as Administrator

$ErrorActionPreference = "Stop"

Write-Host "=== YT-DLP WebUI Windows Build ===" -ForegroundColor Cyan

# Check prerequisites
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous builds
if (Test-Path "build") { Remove-Item -Recurse -Force build }
if (Test-Path "dist") { Remove-Item -Recurse -Force dist }

# Build with PyInstaller
Write-Host "Running PyInstaller..." -ForegroundColor Cyan
pyinstaller yt-dlp-webui.spec --clean --noconfirm

# Check if NSIS is available for installer
if (Get-Command "makensis" -ErrorAction SilentlyContinue) {
    Write-Host "Building NSIS installer..." -ForegroundColor Cyan
    
    # Create NSIS script
    @"
!define APP_NAME "YT-DLP WebUI"
!define APP_VERSION "1.0.0"
!define PUBLISHER "Ash96534"
!define INSTALLER_NAME "YT-DLP-WebUI-1.0.0-Setup.exe"

!include "MUI2.nsh"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "dist/${INSTALLER_NAME}"
InstallDir "C:\Program Files\${APP_NAME}"

Section "MainSection" SEC01
  SetOutPath $INSTDIR
  File /r "dist\yt-dlp-webui\*"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\yt-dlp-webui.exe"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\yt-dlp-webui.exe"
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\yt-dlp-webui.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
SectionEnd
"@ | Out-File -FilePath "installer.nsi" -Encoding UTF8

    makensis installer.nsi
    Write-Host "Installer created: dist\YT-DLP-WebUI-1.0.0-Setup.exe" -ForegroundColor Green
} else {
    Write-Host "NSIS not found. Install NSIS to create installer." -ForegroundColor Yellow
    Write-Host "Portable build available at: dist\yt-dlp-webui\yt-dlp-webui.exe" -ForegroundColor Green
}

Write-Host "=== Build Complete ===" -ForegroundColor Green
