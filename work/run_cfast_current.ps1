# Current v30 grouped fuel scenario with audited room clear heights; unchanged CFAST engine.
# Add --force to measure a fresh calculation; identical complete runs otherwise reuse results.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = 'C:/Users/<user>/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython (Join-Path $PSScriptRoot 'cad_cfast_multifloor.py') --ignition-config (Join-Path $PSScriptRoot 'cfast_fuel_groups_v30.json') --ceiling-config (Join-Path $PSScriptRoot 'cfast_ceiling_heights_v30.json') --output 'CAD-가연물묶음-v30/ceiling' --max-time-step 0.25 @args
if ($LASTEXITCODE -ne 0) { throw 'CFAST calculation or result validation failed' }
