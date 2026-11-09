#Requires -Version 5.1
param([string]$DriveLetter, [string]$PackageRoot = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
$manifest = Get-Content -LiteralPath (Join-Path $PackageRoot 'update.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.file -ne 'filesystem.squashfs' -or
    $manifest.new_sha256 -notmatch '^[a-f0-9]{64}$' -or $manifest.old_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Guncelleme manifesti gecersiz.' }
$accepted = @($manifest.old_sha256)
if ($manifest.accepted_old_sha256) { $accepted += @($manifest.accepted_old_sha256) }
foreach ($value in $accepted) { if ($value -notmatch '^[a-f0-9]{64}$') { throw 'Kaynak surum ozeti gecersiz.' } }
$allowed = $accepted + @($manifest.new_sha256)
$source = Join-Path $PackageRoot 'filesystem.squashfs'
if ((Get-Item -LiteralPath $source).Length -ne $manifest.bytes -or (Hash $source) -ne $manifest.new_sha256) { throw 'Paket eksik veya bozuk. USB degistirilmedi.' }
$hasGrub = [bool]$manifest.grub_file
if ($hasGrub) {
    if ($manifest.grub_file -ne 'grub.cfg' -or $manifest.grub_new_sha256 -notmatch '^[a-f0-9]{64}$' -or $manifest.grub_old_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Acilis ayari manifesti gecersiz.' }
    $grubSource = Join-Path $PackageRoot 'grub.cfg'
    if ((Hash $grubSource) -ne $manifest.grub_new_sha256) { throw 'Paketin acilis ayari bozuk.' }
}
Write-Host 'VEDT 0.7 - USB guncellemesi' -ForegroundColor Cyan
Write-Host 'Raporlar, numarator ve Windows dosyalari korunur.'
Get-Volume | Where-Object FileSystemLabel -eq 'DTLIVE' | Format-Table DriveLetter,FileSystemLabel,SizeRemaining
if (-not $DriveLetter) { $DriveLetter = Read-Host 'DTLIVE bolumunun harfini yazin (ornek E)' }
$DriveLetter = $DriveLetter.Trim().TrimEnd(':').ToUpperInvariant()
if ($DriveLetter -notmatch '^[A-Z]$' -or ($DriveLetter + ':') -eq $env:SystemDrive) { throw 'Gecersiz surucu.' }
$volume = Get-Volume -DriveLetter $DriveLetter
$partition = Get-Partition -DriveLetter $DriveLetter
$disk = Get-Disk -Number $partition.DiskNumber
if ($volume.FileSystemLabel -ne 'DTLIVE' -or $volume.FileSystem -ne 'FAT32' -or $disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem -or $disk.IsReadOnly) { throw 'Yazilabilir VEDT USB bolumu dogrulanamadi. Hicbir dosya degistirilmedi.' }
$root = $DriveLetter + ':\'
$target = Join-Path $root 'live\filesystem.squashfs'
$checksums = Join-Path $root 'sha256sum.txt'
$oldHash = Hash $target
if ($oldHash -notin $allowed) { throw 'Bu USB desteklenen VEDT 0.5/0.6 surumu degil. USB degistirilmedi.' }
$originalChecksums = [IO.File]::ReadAllText($checksums, [Text.Encoding]::UTF8)
$pattern = '(?m)^([a-f0-9]{64})  \./live/filesystem\.squashfs\r?$'
$rootMatches = [regex]::Matches($originalChecksums, $pattern)
if ($rootMatches.Count -ne 1 -or $rootMatches[0].Groups[1].Value -notin $allowed) { throw 'USB ozet listesi eslesmiyor.' }
$grubAlready = $true
if ($hasGrub) {
    $grubTarget = Join-Path $root 'boot\grub\grub.cfg'
    $grubHash = Hash $grubTarget
    $grubAllowed = @($manifest.grub_old_sha256, $manifest.grub_new_sha256)
    if ($grubHash -notin $grubAllowed) { throw 'USB acilis ayari taninmiyor. USB degistirilmedi.' }
    $grubPattern = '(?m)^([a-f0-9]{64})  \./boot/grub/grub\.cfg\r?$'
    $grubMatches = [regex]::Matches($originalChecksums, $grubPattern)
    if ($grubMatches.Count -ne 1 -or $grubMatches[0].Groups[1].Value -notin $grubAllowed) { throw 'Acilis ayari ozet kaydi eslesmiyor.' }
    $grubAlready = $grubHash -eq $manifest.grub_new_sha256 -and $grubMatches[0].Groups[1].Value -eq $manifest.grub_new_sha256
}
if ($oldHash -eq $manifest.new_sha256 -and $rootMatches[0].Groups[1].Value -eq $manifest.new_sha256 -and $grubAlready) { Write-Host 'USB zaten guncel.' -ForegroundColor Green; exit 0 }
if ($volume.SizeRemaining + (Get-Item -LiteralPath $target).Length -lt $manifest.bytes + 8MB) { throw 'DTLIVE bolumunde yer yetersiz.' }
$backupBase = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'VEDT-USB-Yedekleri'
$backupDrive = [IO.Path]::GetPathRoot($backupBase).TrimEnd('\').TrimEnd(':')
if ($backupDrive -eq $DriveLetter) { throw 'Yedek, guncellenen USB uzerine alinamaz.' }
if ((Get-Volume -DriveLetter $backupDrive).SizeRemaining -lt (Get-Item -LiteralPath $target).Length + 64MB) { throw 'Bilgisayarda yedek icin yer yetersiz.' }
Write-Host "USB: $DriveLetter`: / Disk $($disk.Number) / $($disk.FriendlyName)" -ForegroundColor Yellow
if ((Read-Host 'Yalniz test yazilimini guncellemek icin EVET yazin').Trim().ToUpperInvariant() -ne 'EVET') { exit 0 }
$backup = Join-Path $backupBase ([DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$backupRoot = Join-Path $backup 'filesystem.squashfs'
Copy-Item -LiteralPath $target -Destination $backupRoot
Copy-Item -LiteralPath $checksums -Destination (Join-Path $backup 'sha256sum.txt')
if ((Hash $backupRoot) -ne $oldHash) { throw 'Yedek dogrulanamadi; USB degistirilmedi.' }
$attributes = (Get-Item -LiteralPath $target).Attributes
if ($hasGrub) {
    Copy-Item -LiteralPath $grubTarget -Destination (Join-Path $backup 'grub.cfg')
    if ((Hash (Join-Path $backup 'grub.cfg')) -ne $grubHash) { throw 'Acilis yedegi dogrulanamadi.' }
    $grubAttributes = (Get-Item -LiteralPath $grubTarget).Attributes
}
try {
    (Get-Item -LiteralPath $target).IsReadOnly = $false
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Hash $target) -ne $manifest.new_sha256) { throw 'USB yazilim kopyasi dogrulanamadi.' }
    $updated = [regex]::Replace($originalChecksums, $pattern, $manifest.new_sha256 + '  ./live/filesystem.squashfs')
    if ($hasGrub) {
        (Get-Item -LiteralPath $grubTarget).IsReadOnly = $false
        Copy-Item -LiteralPath $grubSource -Destination $grubTarget -Force
        if ((Hash $grubTarget) -ne $manifest.grub_new_sha256) { throw 'Acilis ayari kopyasi dogrulanamadi.' }
        $updated = [regex]::Replace($updated, $grubPattern, $manifest.grub_new_sha256 + '  ./boot/grub/grub.cfg')
    }
    [IO.File]::WriteAllText($checksums + '.new', $updated, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath ($checksums + '.new') -Destination $checksums -Force
} catch {
    $failure = $_
    Write-Host 'Guncelleme tamamlanamadi; eski yazilim geri yukleniyor.' -ForegroundColor Red
    try {
        (Get-Item -LiteralPath $target).IsReadOnly = $false
        Copy-Item -LiteralPath $backupRoot -Destination $target -Force
        if ($hasGrub) {
            (Get-Item -LiteralPath $grubTarget).IsReadOnly = $false
            Copy-Item -LiteralPath (Join-Path $backup 'grub.cfg') -Destination $grubTarget -Force
            if ((Hash $grubTarget) -ne $grubHash) { throw 'Acilis geri yuklemesi dogrulanamadi.' }
        }
        Copy-Item -LiteralPath (Join-Path $backup 'sha256sum.txt') -Destination $checksums -Force
        if ((Hash $target) -ne $oldHash) { throw 'Yazilim geri yuklemesi dogrulanamadi.' }
    } catch { Write-Host "Geri yukleme tamamlanamadi. USB'yi yeniden imajlayin. Yedek: $backup" -ForegroundColor Red }
    throw $failure
} finally {
    if (Test-Path -LiteralPath $target) { (Get-Item -LiteralPath $target).Attributes = $attributes }
    if ($hasGrub -and (Test-Path -LiteralPath $grubTarget)) { (Get-Item -LiteralPath $grubTarget).Attributes = $grubAttributes }
}
Write-Host 'Guncelleme tamamlandi. USB guvenli cikarma islemini kullanin.' -ForegroundColor Green
Write-Host 'Yarim is varsa acilista R + Enter, ardindan SIL + Enter kullanin.'
Write-Host "Eski yazilim ve acilis ayari yedegi: $backup"
