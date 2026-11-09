#Requires -Version 5.1
param([string]$DriveLetter, [string]$PackageRoot = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
$manifest = Get-Content -LiteralPath (Join-Path $PackageRoot 'update.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.file -ne 'filesystem.squashfs' -or
    $manifest.new_sha256 -notmatch '^[a-f0-9]{64}$' -or $manifest.old_sha256 -notmatch '^[a-f0-9]{64}$') {
    throw 'Guncelleme manifesti gecersiz.'
}
$source = Join-Path $PackageRoot 'filesystem.squashfs'
if ((Get-Item -LiteralPath $source).Length -ne $manifest.bytes -or (Hash $source) -ne $manifest.new_sha256) {
    throw 'Paket eksik veya bozuk. USB degistirilmedi.'
}
Write-Host 'VEDT 0.6 - USB guncellemesi' -ForegroundColor Cyan
Write-Host 'Raporlar, numarator ve Windows dosyalari korunur. USB bu bilgisayarda takili olmali.'
Get-Volume | Where-Object FileSystemLabel -eq 'DTLIVE' | Format-Table DriveLetter,FileSystemLabel,SizeRemaining
if (-not $DriveLetter) { $DriveLetter = Read-Host 'DTLIVE bolumunun harfini yazin (ornek E)' }
$DriveLetter = $DriveLetter.Trim().TrimEnd(':').ToUpperInvariant()
if ($DriveLetter -notmatch '^[A-Z]$' -or ($DriveLetter + ':') -eq $env:SystemDrive) { throw 'Gecersiz surucu.' }
$volume = Get-Volume -DriveLetter $DriveLetter
$partition = Get-Partition -DriveLetter $DriveLetter
$disk = Get-Disk -Number $partition.DiskNumber
if ($volume.FileSystemLabel -ne 'DTLIVE' -or $volume.FileSystem -ne 'FAT32' -or
    $disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem -or $disk.IsReadOnly) {
    throw 'Yazilabilir VEDT USB bolumu dogrulanamadi. Hicbir dosya degistirilmedi.'
}
$root = $DriveLetter + ':\'
$target = Join-Path $root 'live\filesystem.squashfs'
$checksums = Join-Path $root 'sha256sum.txt'
$oldHash = Hash $target
if ($oldHash -eq $manifest.new_sha256) { Write-Host 'USB zaten guncel.' -ForegroundColor Green; exit 0 }
if ($oldHash -ne $manifest.old_sha256) { throw 'Bu USB desteklenen 0.5 imaji degil. USB degistirilmedi.' }
$originalChecksums = [IO.File]::ReadAllText($checksums, [Text.Encoding]::UTF8)
$pattern = '(?m)^' + [regex]::Escape($oldHash) + '  \./live/filesystem\.squashfs\r?$'
if ([regex]::Matches($originalChecksums, $pattern).Count -ne 1) { throw 'USB ozet listesi eslesmiyor.' }
if ($volume.SizeRemaining + (Get-Item -LiteralPath $target).Length -lt $manifest.bytes + 8MB) {
    throw 'DTLIVE bolumunde yeni yazilim icin yer yetersiz.'
}
$backupBase = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'VEDT-USB-Yedekleri'
$backupDrive = [IO.Path]::GetPathRoot($backupBase).TrimEnd('\').TrimEnd(':')
if ($backupDrive -eq $DriveLetter) { throw 'Yedek, guncellenen USB uzerine alinamaz.' }
$backupVolume = Get-Volume -DriveLetter $backupDrive
if ($backupVolume.SizeRemaining -lt (Get-Item -LiteralPath $target).Length + 64MB) { throw 'Bilgisayarda yedek icin bos alan yetersiz.' }
Write-Host "USB: $DriveLetter`: / Disk $($disk.Number) / $($disk.FriendlyName)" -ForegroundColor Yellow
if ((Read-Host 'Yalniz test yazilimini guncellemek icin EVET yazin').Trim().ToUpperInvariant() -ne 'EVET') { exit 0 }
$backup = Join-Path $backupBase ([DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$backupRoot = Join-Path $backup 'filesystem.squashfs'
Copy-Item -LiteralPath $target -Destination $backupRoot
Copy-Item -LiteralPath $checksums -Destination (Join-Path $backup 'sha256sum.txt')
if ((Hash $backupRoot) -ne $oldHash) { throw 'Yedek dogrulanamadi; USB degistirilmedi.' }
$attributes = (Get-Item -LiteralPath $target).Attributes
try {
    (Get-Item -LiteralPath $target).IsReadOnly = $false
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Hash $target) -ne $manifest.new_sha256) { throw 'USB kopyasi dogrulanamadi.' }
    $updated = [regex]::Replace($originalChecksums, $pattern, $manifest.new_sha256 + '  ./live/filesystem.squashfs')
    [IO.File]::WriteAllText($checksums + '.new', $updated, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath ($checksums + '.new') -Destination $checksums -Force
} catch {
    $failure = $_
    Write-Host 'Guncelleme tamamlanamadi; eski yazilim geri yukleniyor.' -ForegroundColor Red
    try {
        Copy-Item -LiteralPath $backupRoot -Destination $target -Force
        Copy-Item -LiteralPath (Join-Path $backup 'sha256sum.txt') -Destination $checksums -Force
        if ((Hash $target) -ne $oldHash) { throw 'Geri yukleme dogrulanamadi.' }
    } catch { Write-Host "Geri yukleme tamamlanamadi. USB'yi yeniden imajlayin. Yedek: $backup" -ForegroundColor Red }
    throw $failure
} finally {
    if (Test-Path -LiteralPath $target) { (Get-Item -LiteralPath $target).Attributes = $attributes }
}
Write-Host 'Guncelleme tamamlandi. USB guvenli cikarma islemini kullanin.' -ForegroundColor Green
Write-Host 'USB ile acilista yarim is icin R + Enter, ardindan SIL + Enter kullanin.'
Write-Host "Eski yazilim yedegi: $backup"
