param(
    [string]$Scenario = 'examples\three_rooms.json',
    [string]$Output = 'results\three_rooms',
    [switch]$Build
)
$ErrorActionPreference = 'Stop'
$bundledPythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonRuntimePath = if (Test-Path -LiteralPath $bundledPythonPath) { $bundledPythonPath } else { (Get-Command python).Source }
Push-Location -LiteralPath $PSScriptRoot
try {
    if ($Build -or !(Test-Path -LiteralPath 'build\cfbt\cfast-cfbt.exe')) {
        & $pythonRuntimePath -X utf8 'tools\build_engine.py' cfbt
        if ($LASTEXITCODE -ne 0) { throw 'Engine build failed' }
    }
    & $pythonRuntimePath -X utf8 -m pyrocast_cfbt $Scenario --output $Output
    if ($LASTEXITCODE -ne 0) { throw 'CFBT simulation failed; inspect output/logs' }
}
finally { Pop-Location }
