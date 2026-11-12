$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\..\..\FireLapse-Retention.ps1')
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('firelapse-retention-' + [guid]::NewGuid().ToString('N'))
$releases = Join-Path $tempRoot 'releases'
function Assert($ok, $message) { if (-not $ok) { throw $message } }
function Add-Release($name) {
    $dir = Join-Path $releases $name
    [void][IO.Directory]::CreateDirectory($dir)
    # As shipped: UTF-8 without BOM with Korean model labels. Read as ANSI, this label breaks the JSON on a Korean Windows.
    $label = -join [char[]](0xD30C,0xD06C,0xB9C8,0xB9B0,0xD638,0xD154,0x20,0xB7,0x20,0xBCF4,0xC815,0xBCF8)
    $json = @{name='FireLapse';version=$name.Substring(1);models=@(@{label=$label})} | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $dir 'distribution.json'), $json, (New-Object Text.UTF8Encoding $false))
}
try {
    foreach ($v in @('v2026.11.07-r8','v2026.11.07-r9','v2026.11.07-r10','v2026.11.07-r11','v2026.11.07-r12','v2026.11.07-r13','v2026.11.07-r14')) { Add-Release $v }
    $results = Join-Path $tempRoot 'results'
    [void][IO.Directory]::CreateDirectory($results)
    $sentinel = Join-Path $results 'calculation.json'
    'preserve calculation bytes' | Set-Content -LiteralPath $sentinel
    $before = (Get-FileHash -LiteralPath $sentinel).Hash
    $unknown = Join-Path $releases 'v2026.11.07-r7'
    [void][IO.Directory]::CreateDirectory($unknown)
    $running = Join-Path $releases 'v2026.11.07-r11\runtime\python.exe'
    $removed = @(Remove-FireLapseOldReleases $releases 'v2026.11.07-r13' -ProcessPaths @($running))
    Assert ($removed.Count -eq 3) 'Expected r8/r9/r10 removal (numeric revision ordering).'
    foreach ($v in @('v2026.11.07-r11','v2026.11.07-r12','v2026.11.07-r13','v2026.11.07-r14','v2026.11.07-r7')) {
        Assert (Test-Path -LiteralPath (Join-Path $releases $v)) "Protected folder lost: $v"
    }
    Assert ((Get-FileHash -LiteralPath $sentinel).Hash -eq $before) 'Calculation data changed.'
    $retry = @(Remove-FireLapseOldReleases $releases 'v2026.11.07-r13' -ProcessPaths @())
    Assert ($retry.Count -eq 1 -and $retry[0] -eq 'v2026.11.07-r11') 'Stopped release was not retried.'
    Assert (@(Remove-FireLapseOldReleases $releases 'v2026.11.07-r13' -ProcessPaths @()).Count -eq 0) 'Cleanup not idempotent.'
    $failed = $false
    try { Remove-FireLapseOldReleases $releases 'v2026.11.08-r1' -ProcessPaths @() } catch { $failed = $true }
    Assert $failed 'Missing current version must prevent cleanup.'
    Write-Host 'PASS: retention, running release, newer release, unknown directory, results preservation, retry, idempotence, missing current.'
} finally {
    $resolved = [IO.Path]::GetFullPath($tempRoot)
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -eq $parent -and [IO.Path]::GetFileName($resolved).StartsWith('firelapse-retention-')) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
