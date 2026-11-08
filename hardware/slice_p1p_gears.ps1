param([ValidateSet('gears','base','fit','key')][string]$Plate = 'gears')
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path $PSScriptRoot -Parent
$studioPath = Join-Path $env:LOCALAPPDATA 'Programs\BambuStudio-2.9.1-Portable'
$partsPath = Join-Path $PSScriptRoot 'print_parts'
$settingsPath = Join-Path $partsPath 'p1p_profiles'
$finalPath = Join-Path $PSScriptRoot 'final files'
$jobs = @{
    gears = @('gears_and_spacers_P1P.3mf', '02_gears_and_washers_P1P_PLA.gcode.3mf')
    base = @('base_and_legs_key_settings.3mf', '01_BASE_WIDE_KEYS_BRIM_P1P_PLA.gcode.3mf')
    fit = @('boltless_fit_test.3mf', '00_boltless_fit_test_P1P_PLA.gcode.3mf')
    key = @('locking_key_retry.3mf', '04_WIDE_T_KEY_ZERO_GAP_P1P_PLA.gcode.3mf')
}
$inputName, $outputName = $jobs[$Plate]
$processProfile = switch ($Plate) { 'fit' {'process_fit.json'} 'key' {'process_key.json'} 'base' {'process_base.json'} default {'process.json'} }
$filamentProfile = switch ($Plate) { 'fit' {'filament_fit.json'} 'key' {'filament_key.json'} 'base' {'filament_key.json'} default {'filament.json'} }
$bambuTempPath = Join-Path $workspacePath 'tmp\bambu-temp'
New-Item -ItemType Directory -Force $finalPath,$bambuTempPath,(Join-Path $workspacePath 'tmp\bambu-profile') | Out-Null
$arguments = @(
    '--debug', '2',
    '--datadir', ('"' + (Join-Path $workspacePath 'tmp\bambu-profile') + '"'),
    '--curr-bed-type', '"Textured PEI Plate"',
    '--load-settings', ('"' + (Join-Path $settingsPath 'machine.json') + ';' + (Join-Path $settingsPath $processProfile) + '"'),
    '--load-filaments', ('"' + (Join-Path $settingsPath $filamentProfile) + '"'),
    '--arrange', '0', '--slice', '0',
    '--export-3mf', ('"' + (Join-Path $finalPath $outputName) + '"'),
    ('"' + (Join-Path $partsPath $inputName) + '"')
)
$process = Start-Process -FilePath (Join-Path $studioPath 'bambu-studio.exe') `
    -ArgumentList $arguments -WorkingDirectory $studioPath -NoNewWindow -Wait -PassThru `
    -Environment @{TEMP=$bambuTempPath; TMP=$bambuTempPath}
Write-Output "Slicer exit code: $($process.ExitCode)"
if ($process.ExitCode -ne 0) { throw 'Bambu Studio slicing failed.' }
if (-not (Test-Path -LiteralPath (Join-Path $finalPath $outputName))) {
    throw 'No sliced output was produced.'
}
