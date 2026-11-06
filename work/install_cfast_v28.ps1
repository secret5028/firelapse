$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOut = Join-Path $taskRoot 'outputs/CAD-연소표현-v28'
$taskApp = 'C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱'
$taskJob = Join-Path $taskApp 'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
$taskTemplate = Join-Path $taskApp '_internal/cad_engine/integrated_viewer.html'
$taskReport = Get-Content -LiteralPath (Join-Path $taskOut '검증결과.json') -Raw | ConvertFrom-Json
if ($taskReport.status -ne 'passed') { throw 'Verification required' }
if ((Get-FileHash -LiteralPath (Join-Path $taskJob 'building.json')).Hash.ToLower() -ne $taskReport.building_sha256) { throw 'Building changed' }
foreach ($taskName in @('model.html','cfast-demo.json')) {
    $taskCurrent = (Get-FileHash -LiteralPath (Join-Path $taskJob $taskName)).Hash
    $taskBackup = (Get-FileHash -LiteralPath (Join-Path $taskOut ('backup/'+$taskName))).Hash
    $taskNew = (Get-FileHash -LiteralPath (Join-Path $taskOut $taskName)).Hash
    if ($taskCurrent -ne $taskBackup -and $taskCurrent -ne $taskNew) { throw "Installed file changed: $taskName" }
}
if ((Get-FileHash -LiteralPath (Join-Path $taskOut 'model.html')).Hash.ToLower() -ne $taskReport.model_sha256) { throw 'Viewer not verified' }
if ((Get-FileHash -LiteralPath (Join-Path $taskOut 'cfast-demo.json')).Hash.ToLower() -ne $taskReport.result_sha256) { throw 'Result not verified' }
$taskTemplateBackup = Join-Path $taskOut 'backup/installed-template.html'
if (!(Test-Path -LiteralPath $taskTemplateBackup)) { Copy-Item -LiteralPath $taskTemplate -Destination $taskTemplateBackup }
Copy-Item -LiteralPath (Join-Path $taskOut 'model.html') -Destination (Join-Path $taskJob 'model.html') -Force
Copy-Item -LiteralPath (Join-Path $taskOut 'cfast-demo.json') -Destination (Join-Path $taskJob 'cfast-demo.json') -Force
Copy-Item -LiteralPath (Join-Path $taskOut 'model.html') -Destination $taskTemplate -Force
@{status='installed';building_sha256=$taskReport.building_sha256;model_sha256=$taskReport.model_sha256;result_sha256=$taskReport.result_sha256;solver_rerun=$false;physical_validation=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOut '설치기록.json') -Encoding utf8
Write-Output 'v28 installed with original building and numerical results preserved.'
