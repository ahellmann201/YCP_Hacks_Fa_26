param([string]$Serial = '')
$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe'
if (-not (Test-Path -LiteralPath $adb)) { throw 'Arduino adb tool not found. Install the UNO Q board package first.' }
$devices = @(& $adb devices | Where-Object {$_ -match '^\S+\s+device$'} | ForEach-Object {($_ -split '\s+')[0]})
if (-not $Serial) {
    if ($devices.Count -ne 1) { throw 'Connect exactly one UNO Q, or supply -Serial with its USB serial number.' }
    $Serial=$devices[0]
}
& $adb -s $Serial forward tcp:8765 tcp:8765
if ($LASTEXITCODE -ne 0) { throw 'USB forwarding failed. Reconnect the board.' }
$status=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/status' -Headers @{'X-Scanner-Motor'='1'} -TimeoutSec 5
if ($status.protocol -ne 1) { throw 'The automatic-scan firmware/agent is not ready.' }
Write-Output "UNO Q connected. Motor state: $($status.state) (0 idle, 3 done, 4 stopped)."
