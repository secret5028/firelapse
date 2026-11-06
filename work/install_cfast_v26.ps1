$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOutput = Join-Path $taskRoot 'outputs/CAD-조건부전이-v26'
$taskApp = 'C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱'
$taskJob = Join-Path $taskApp 'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
$taskVerification = Get-Content -LiteralPath (Join-Path $taskOutput '검증결과.json') -Raw | ConvertFrom-Json
if ($taskVerification.status -ne 'passed') { throw 'Verification is not passed' }
$taskBuilding = (Get-FileHash -LiteralPath (Join-Path $taskJob 'building.json') -Algorithm SHA256).Hash.ToLower()
if ($taskBuilding -ne $taskVerification.building_sha256) { throw 'Building changed since calculation' }
if (!(Test-Path -LiteralPath (Join-Path $taskOutput 'backup/model.html'))) { throw 'Missing rollback backup' }
Copy-Item -LiteralPath (Join-Path $taskOutput 'cfast-demo.json') -Destination (Join-Path $taskJob 'cfast-demo.json') -Force
Copy-Item -LiteralPath (Join-Path $taskOutput 'model.html') -Destination (Join-Path $taskJob 'model.html') -Force
Copy-Item -LiteralPath (Join-Path $taskOutput 'model.html') -Destination (Join-Path $taskApp '_internal/cad_engine/integrated_viewer.html') -Force
Write-Output 'NIST scenario and viewer installed; building unchanged.'
