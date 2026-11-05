#!/bin/bash
# Build script for Linux/macOS - creates portable binary and AppImage
# Requires: pip install pyinstaller appimage-tool
set -e

echo "=== YT-DLP WebUI Linux/macOS Build ==="

# Check prerequisites
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
echo "Running PyInstaller..."
pyinstaller yt-dlp-webui.spec --clean --noconfirm

# Create AppImage for Linux
if command -v appimagetool &> /dev/null; then
    echo "Building AppImage..."
    APPDIR="dist/yt-dlp-webui.AppDir"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
    
    # Copy binary
    cp "dist/yt-dlp-webui/yt-dlp-webui" "$APPDIR/usr/bin/"
    chmod +x "$APPDIR/usr/bin/yt-dlp-webui"
    
    # Desktop entry
    cat > "$APPDIR/usr/share/applications/yt-dlp-webui.desktop" << EOF
[Desktop Entry]
Name=YT-DLP WebUI
Comment=YouTube Browser with Integrated Downloader
Exec=yt-dlp-webui
Icon=yt-dlp-webui
Type=Application
Categories=AudioVideo;Network;
EOF

    # Icon (placeholder - replace with actual icon)
    cp "ffmpeg/bin/ffmpeg.exe" "$APPDIR/usr/share/icons/hicolor/256x256/apps/yt-dlp-webui.png" 2>/dev/null || true
    
    # AppRun script
    cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
exec ./usr/bin/yt-dlp-webui "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    appimagetool "$APPDIR" "dist/YT-DLP-WebUI-1.0.0-x86_64.AppImage"
    echo "AppImage created: dist/YT-DLP-WebUI-1.0.0-x86_64.AppImage"
else
    echo "AppImageTool not found. Portable binary at: dist/yt-dlp-webui/yt-dlp-webui"
fi

echo "=== Build Complete ==="