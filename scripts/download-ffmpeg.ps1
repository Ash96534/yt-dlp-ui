# Download FFmpeg Windows essentials build and extract to ffmpeg/bin
$ProgressPreference = 'SilentlyContinue'
$zipPath = "$PSScriptRoot\..\ffmpeg\ffmpeg.zip"
$extractDir = "$PSScriptRoot\..\ffmpeg"
$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

Write-Host "Downloading FFmpeg from $url ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $zipPath

Write-Host "Extracting ..." -ForegroundColor Cyan
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# Move bin/ffmpeg.exe and bin/ffprobe.exe into ffmpeg/bin/
$innerDir = Get-ChildItem -Path $extractDir | Where-Object { $_.PSIsContainer -and $_.Name -like "ffmpeg-*" } | Select-Object -First 1
if ($innerDir) {
    Move-Item -Path "$($innerDir.FullName)\bin\ffmpeg.exe" -Destination "$extractDir\bin\ffmpeg.exe" -Force
    Move-Item -Path "$($innerDir.FullName)\bin\ffprobe.exe" -Destination "$extractDir\bin\ffprobe.exe" -Force
    Remove-Item -Path $innerDir.FullName -Recurse -Force
}

Remove-Item -Path $zipPath -Force
Write-Host "FFmpeg ready at $extractDir\bin\ffmpeg.exe" -ForegroundColor Green
