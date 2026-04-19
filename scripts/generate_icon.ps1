#Requires -Version 5
# Convert a PNG into docs/images/flower.ico (multi-size).
#
# Usage:
#   .\generate_icon.ps1                                # uses docs/images/icon-source.png
#   .\generate_icon.ps1 -Source path\to\your.png       # uses a custom input
#
# Note: the repo ships with docs/images/icon-source.svg — open it in any image
# editor (Inkscape, Figma, GIMP, Photoshop, Affinity...) and export it as a
# square PNG (at least 256x256) to feed this script. PowerShell's built-in
# System.Drawing can't rasterize SVG, so the PNG step stays manual.

param(
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$repo = Split-Path -Parent $PSScriptRoot
if (-not $Source) {
    $Source = Join-Path $repo "docs/images/icon-source.png"
}
$dst = Join-Path $repo "docs/images/flower.ico"

if (-not (Test-Path $Source)) {
    Write-Error "Source PNG not found: $Source"
    Write-Host "Tip: open docs/images/icon-source.svg in an image editor and export it as PNG first."
    exit 1
}

$sourceImg = [System.Drawing.Image]::FromFile($Source)
$sizes = @(256, 128, 64, 48, 32, 16)

# Create each size as a bitmap in memory
$images = @()
foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $gfx.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $gfx.PixelOffsetMode   = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $gfx.Clear([System.Drawing.Color]::Transparent)
    $gfx.DrawImage($sourceImg, 0, 0, $size, $size)
    $gfx.Dispose()
    $images += $bmp
}
$sourceImg.Dispose()

# Serialize ICO manually (Windows .ico format: ICONDIR + ICONDIRENTRY[] + PNG-encoded images)
$ms = New-Object System.IO.MemoryStream
$w  = New-Object System.IO.BinaryWriter($ms)

# ICONDIR
$w.Write([uint16]0)                   # reserved
$w.Write([uint16]1)                   # type: 1 = ICO
$w.Write([uint16]$images.Count)       # count

# Convert each image to PNG bytes
$pngBlobs = @()
foreach ($bmp in $images) {
    $s = New-Object System.IO.MemoryStream
    $bmp.Save($s, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngBlobs += ,$s.ToArray()
    $s.Dispose()
    $bmp.Dispose()
}

$headerSize = 6 + ($images.Count * 16)
$offset = $headerSize

# ICONDIRENTRY[]
for ($i = 0; $i -lt $images.Count; $i++) {
    $size = $sizes[$i]
    $blobSize = $pngBlobs[$i].Length
    $w.Write([byte]([math]::Min($size, 255) % 256))  # width (0 = 256)
    $w.Write([byte]([math]::Min($size, 255) % 256))  # height
    $w.Write([byte]0)                 # colors
    $w.Write([byte]0)                 # reserved
    $w.Write([uint16]1)               # planes
    $w.Write([uint16]32)              # bpp
    $w.Write([uint32]$blobSize)       # size
    $w.Write([uint32]$offset)         # offset
    $offset += $blobSize
}

# PNG blobs
foreach ($blob in $pngBlobs) {
    $w.Write($blob)
}

$w.Flush()
[System.IO.File]::WriteAllBytes($dst, $ms.ToArray())
$ms.Dispose()

Write-Host "Icon written: $dst ($($images.Count) sizes)"
