$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOutput = Join-Path $taskRoot 'outputs/CAD-속도검증-v27'
$taskApp = 'C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱'
$taskJob = Join-Path $taskApp 'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
$taskReport = Get-Content -LiteralPath (Join-Path $taskOutput 'full-verification.json') -Raw | ConvertFrom-Json
if (!$taskReport.approved_for_install) { throw 'Full comparison has not been accepted' }
$taskBuilding = (Get-FileHash -LiteralPath (Join-Path $taskJob 'building.json') -Algorithm SHA256).Hash.ToLower()
if ($taskBuilding -ne $taskReport.building_sha256) { throw 'Building changed during calculation' }
$taskSource = Join-Path $taskOutput 'final/cfast-demo.json'
if ((Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash.ToLower() -ne $taskReport.approved_result_sha256) { throw 'Result changed after verification' }
$taskReference = Join-Path $taskRoot 'outputs/CAD-조건부전이-v26/cfast-demo.json'
$taskTarget = Join-Path $taskJob 'cfast-demo.json'
if ((Get-FileHash -LiteralPath $taskTarget).Hash -ne (Get-FileHash -LiteralPath $taskReference).Hash) { throw 'Installed scenario changed; do not overwrite it' }
$taskBackup = Join-Path $taskOutput 'backup'
New-Item -ItemType Directory -Path $taskBackup -Force | Out-Null
Copy-Item -LiteralPath $taskTarget -Destination (Join-Path $taskBackup 'cfast-demo.json')
$taskUiHash = (Get-FileHash -LiteralPath (Join-Path $taskJob 'model.html')).Hash
Copy-Item -LiteralPath $taskSource -Destination $taskTarget -Force
if ((Get-FileHash -LiteralPath (Join-Path $taskJob 'model.html')).Hash -ne $taskUiHash) { throw 'Viewer changed unexpectedly' }
$taskRecord = @{status='installed'; result_sha256=(Get-FileHash -LiteralPath $taskTarget).Hash.ToLower(); viewer_sha256=$taskUiHash.ToLower(); viewer_unchanged=$true; building_sha256=$taskBuilding; physical_validation=$false}
$taskRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOutput '설치기록.json') -Encoding utf8
Write-Output 'Optimized calculation installed; existing viewer and building unchanged.'
