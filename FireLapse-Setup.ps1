$ErrorActionPreference = 'Stop'

$version = 'v2026.11.07-r4'
$archiveName = 'FireLapse-Windows-x64-2026.11.07-r4.zip'
$releaseUrl = "https://github.com/secret5028/firelapse/releases/download/$version/$archiveName"
$expectedHash = '9ded49ff011735ba0dedcf6ec8edce9c24b3d076777b9cab4a3d73adc32c2c3a'
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'FireLapse\releases'))
$installDir = Join-Path $releaseRoot $version
$launcher = Join-Path $installDir 'FireLapse.cmd'

function Install-FireLapse {
    if (Test-Path -LiteralPath $launcher -PathType Leaf) { return }

    [void][IO.Directory]::CreateDirectory($releaseRoot)
    $stage = Join-Path $releaseRoot ('.setup-' + [guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($stage)
    try {
        $archive = Join-Path $stage $archiveName
        Write-Host "Downloading FireLapse $version (418 MB)..."
        & "$env:SystemRoot\System32\curl.exe" --fail --location --retry 2 --progress-bar --output $archive $releaseUrl
        if ($LASTEXITCODE -ne 0) { throw 'Download failed. Check your internet connection and try again.' }
        $sha256 = [Security.Cryptography.SHA256]::Create()
        $stream = [IO.File]::OpenRead($archive)
        try { $hash = [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '') }
        finally {
            $stream.Dispose()
            $sha256.Dispose()
        }
        if ($hash -ne $expectedHash) {
            throw 'The downloaded ZIP failed its SHA-256 check. Run FireLapse.cmd again to retry.'
        }

        Write-Host 'Extracting FireLapse (about 3.2 GB)...'
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $stage)
        $package = Join-Path $stage 'FireLapse'
        if (-not (Test-Path -LiteralPath (Join-Path $package 'FireLapse.cmd') -PathType Leaf)) {
            throw 'The ZIP is missing the FireLapse launcher.'
        }
        [IO.Directory]::Move($package, $installDir)
    }
    finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}

try {
    $mutex = New-Object System.Threading.Mutex($false, "Local\FireLapse-Setup-$version")
    try {
        try { [void]$mutex.WaitOne() }
        catch [System.Threading.AbandonedMutexException] { }
        try { Install-FireLapse }
        finally { $mutex.ReleaseMutex() }
    }
    finally { $mutex.Dispose() }

    try {
        $icon = Join-Path $installDir 'FireLapse.ico'
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'FireLapse.ico') -Destination $icon -Force
        $desktop = [Environment]::GetFolderPath('DesktopDirectory')
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path $desktop 'FireLapse.lnk'))
        $shortcut.TargetPath = $launcher
        $shortcut.WorkingDirectory = $installDir
        $shortcut.Description = 'FireLapse - compartment fire timeline'
        $shortcut.IconLocation = "$icon,0"
        $shortcut.Save()
    }
    catch { Write-Warning "Could not create the desktop shortcut. $($_.Exception.Message)" }

    & $launcher
    exit $LASTEXITCODE
}
catch {
    [Console]::Error.WriteLine("FireLapse setup failed. $($_.Exception.Message)")
    exit 1
}
