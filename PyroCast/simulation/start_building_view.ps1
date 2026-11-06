param(
    [string]$Project = 'C:\Users\<user>\Documents\Codex\2026-10-14\files-pasted-by-the-user-cad3d',
    [int]$Port = 8780,
    [string]$Building = ''
)
$ErrorActionPreference = 'Stop'
$bundledPythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonRuntimePath = if (Test-Path -LiteralPath $bundledPythonPath) { $bundledPythonPath } else { (Get-Command python).Source }
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    $wholeResult = Join-Path $PSScriptRoot 'results\cad_whole_verified\playback.json'
    $floorResult = Join-Path $PSScriptRoot 'results\cad_floor\playback.json'
    $openingResult = Join-Path $PSScriptRoot 'results\cad_opening_30min\playback.json'
    $practicalResult = Join-Path $PSScriptRoot 'results\cad_practical_30min\playback.json'
    $floorSmokeResult = Join-Path $PSScriptRoot 'results\cad_floor_smoke_v5_prescribed\playback.json'
    $riskResult = Join-Path $PSScriptRoot 'results\condition_display_v1\playback.json'
    if (-not (Test-Path -LiteralPath $riskResult)) { $riskResult = Join-Path $PSScriptRoot 'results\cad_exterior_risk_demo_v4_ceiling\playback.json' }
    $playbackResult = if (Test-Path -LiteralPath $floorSmokeResult) { $floorSmokeResult } elseif (Test-Path -LiteralPath $riskResult) { $riskResult } elseif (Test-Path -LiteralPath $practicalResult) { $practicalResult } elseif (Test-Path -LiteralPath $openingResult) { $openingResult } elseif (Test-Path -LiteralPath $wholeResult) { $wholeResult } else { $floorResult }
    $viewerArguments=@('-X','utf8','tools\serve_cfbt_building.py',$Project,'--port',"$Port",'--result',$playbackResult)
    if ($Building) { $viewerArguments+=@('--building',$Building) }
    & $pythonRuntimePath @viewerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Building viewer server stopped with an error' }
}
finally { Pop-Location }
