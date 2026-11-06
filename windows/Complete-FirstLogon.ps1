# Yalnız oluşturulan test kullanıcısının ilk oturumunda çalıştırılır.
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:ProgramData 'DiskTest86'
$result = @{ completed = $false; account = $env:USERNAME; computer = $env:COMPUTERNAME }
try {
    $expected = (Get-Content -LiteralPath (Join-Path $base 'expected-manifest.txt') -Raw).Trim()
    & (Join-Path $base 'Apply-TestDesktop.ps1') -ReportSource (Join-Path $base 'test-report') -ExpectedManifestHash $expected
    $desktop = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) $env:USERNAME
    $result.desktop_report = $desktop
    $result.manifest_sha256 = (Get-FileHash -LiteralPath (Join-Path $desktop 'manifest.json') -Algorithm SHA256).Hash.ToLower()
    $result.wallpaper = (Get-ItemProperty -LiteralPath 'HKCU:\Control Panel\Desktop').Wallpaper
    $result.language = (Get-UICulture).Name
    # İlk oturumdan sonra cevap dosyasındaki otomatik oturum ayarları tutulmaz.
    $logon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    Set-ItemProperty -LiteralPath $logon -Name AutoLogonCount -Value 0
    Set-ItemProperty -LiteralPath $logon -Name AutoAdminLogon -Value '0'
    Remove-ItemProperty -LiteralPath $logon -Name DefaultPassword -ErrorAction SilentlyContinue
    $result.completed = $true
} catch {
    $result.completed = $false
    $result.error = $_.Exception.Message
}
$contextPath = Join-Path $base 'deployment-context.json'
if (Test-Path -LiteralPath $contextPath) {
    $context = Get-Content -LiteralPath $contextPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
        $markerPath = Join-Path $drive.Root 'VEDT-MEDIA.json'
        if (Test-Path -LiteralPath $markerPath) {
            $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($marker.role -eq 'reports' -and $marker.media_id -eq $context.media_id -and $context.job_id -match '^[a-f0-9]{24}$' -and $context.report_id -match '^[a-f0-9]{24}$') {
                $recordFolder = Join-Path $drive.Root ('reports/jobs/' + $context.job_id + '/' + $context.report_id)
                if (Test-Path -LiteralPath $recordFolder) {
                    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $recordFolder 'windows-first-logon.json') -Encoding UTF8
                }
            }
        }
    }
}
$text = $result | ConvertTo-Json -Depth 6
$text | Set-Content -LiteralPath (Join-Path $base 'first-logon-result.json') -Encoding UTF8
foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
    if (Test-Path -LiteralPath (Join-Path $drive.Root 'DT-WINPE-LAB.json')) {
        $text | Set-Content -LiteralPath (Join-Path $drive.Root 'first-logon-result.json') -Encoding UTF8
    }
}
try {
    $port = [IO.Ports.SerialPort]::new('COM1',115200)
    $port.DtrEnable = $true
    $port.RtsEnable = $true
    $port.WriteTimeout = 1000
    $port.Open()
    $port.WriteLine('DT_FIRSTLOGON=' + ($result | ConvertTo-Json -Compress -Depth 6))
    $port.Close()
} catch { }
