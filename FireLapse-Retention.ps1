# Only managed installation directories are eligible; shared results are never traversed.
function Remove-FireLapseOldReleases {
    param([Parameter(Mandatory=$true)][string]$ReleaseRoot,
          [Parameter(Mandatory=$true)][string]$CurrentVersion,
          [string[]]$ProcessPaths)
    $root = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd('\')
    $pattern = '^v(\d{4}\.\d{2}\.\d{2})-r(\d+)$'
    if ($CurrentVersion -notmatch $pattern) { throw 'Invalid current version.' }
    $currentKey = $Matches[1] + ('{0:D8}' -f [int]$Matches[2])
    $current = Join-Path $root $CurrentVersion
    if (-not (Test-Path -LiteralPath (Join-Path $current 'distribution.json') -PathType Leaf)) {
        throw 'Current installation is missing; no releases will be removed.'
    }
    if (-not $PSBoundParameters.ContainsKey('ProcessPaths')) {
        # Fail closed if process enumeration is unavailable.
        $ProcessPaths = @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
            if ($_.ExecutablePath) { $_.ExecutablePath }
            if ($_.CommandLine) { $_.CommandLine }
        })
    }
    $rows = @(Get-ChildItem -LiteralPath $root -Directory -Force | ForEach-Object {
        if ($_.Name -match $pattern) {
            [pscustomobject]@{Dir=$_; Key=($Matches[1] + ('{0:D8}' -f [int]$Matches[2]))}
        }
    })
    $previous = $rows | Where-Object { $_.Key -lt $currentKey } | Sort-Object Key -Descending | Select-Object -First 1
    foreach ($row in $rows) {
        $dir = $row.Dir
        if ($row.Key -ge $currentKey -or ($previous -and $dir.Name -eq $previous.Dir.Name)) { continue }
        $target = [IO.Path]::GetFullPath($dir.FullName).TrimEnd('\')
        if ([IO.Path]::GetDirectoryName($target) -ne $root) { throw 'Cleanup target escaped releases directory.' }
        if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Warning "Skipped linked release: $target"; continue }
        $manifest = Join-Path $target 'distribution.json'
        if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { continue }
        $meta = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        if ($meta.name -ne 'FireLapse' -or ('v' + $meta.version) -ne $dir.Name) { continue }
        $prefix = $target + '\'
        if (@($ProcessPaths | Where-Object { $_.IndexOf($prefix, [StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count) {
            Write-Warning "Skipped running release: $target"; continue
        }
        # Do not follow junctions, including a junction into shared calculation data.
        $entries = @(Get-ChildItem -LiteralPath $target -Recurse -Force -ErrorAction Stop)
        if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
            Write-Warning "Skipped release containing links: $target"; continue
        }
        try {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
            Write-Output $dir.Name
        } catch { Write-Warning "Could not remove old release $target : $($_.Exception.Message)" }
    }
}
