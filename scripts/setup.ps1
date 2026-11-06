$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        & py -3 -m venv (Join-Path $projectRoot '.venv')
    } else {
        & python -m venv (Join-Path $projectRoot '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 veya daha yeni sürümü gerekli.' }
}
& $venvPython -m pip install -e "$projectRoot[test]"
if ($LASTEXITCODE -ne 0) { throw 'Bağımlılık kurulumu başarısız.' }
Write-Host 'Kurulum tamamlandı. DEMO-BASLAT.cmd dosyasını açabilirsiniz.'
