$ErrorActionPreference = 'Stop'

$version = 'v2026.11.07-r10'
$archiveName = 'FireLapse-Windows-x64-2026.11.07-r10.zip'
$releaseUrl = "https://github.com/secret5028/firelapse/releases/download/$version/$archiveName"
$expectedHash = '876c31d24876fc5164419985ac9f6323b919bb2b0ebe5ed60d25f46318791305'
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'FireLapse\releases'))
$installDir = Join-Path $releaseRoot $version
$launcher = Join-Path $installDir 'FireLapse.cmd'

function Resolve-ShellTarget($path) {
    # Explorer runs outside the installer and needs the physical file path.
    if (-not ('FireLapseShellPath' -as [type])) {
        Add-Type -TypeDefinition @'
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class FireLapseShellPath {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandle(
        SafeFileHandle file, StringBuilder path, uint capacity, uint flags);

    public static string Resolve(string name) {
        using (var file = File.OpenRead(name)) {
            var path = new StringBuilder(32768);
            var length = GetFinalPathNameByHandle(file.SafeFileHandle, path, (uint)path.Capacity, 0);
            if (length == 0 || length >= path.Capacity) return name;
            var resolved = path.ToString();
            if (resolved.StartsWith(@"\\?\UNC\")) return @"\\" + resolved.Substring(8);
            if (resolved.StartsWith(@"\\?\")) return resolved.Substring(4);
            return resolved;
        }
    }
}
'@
    }
    [FireLapseShellPath]::Resolve($path)
}

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

    $shellTarget = $launcher
    try { $shellTarget = Resolve-ShellTarget $launcher } catch { }
    $shellDirectory = Split-Path -Parent $shellTarget
    $windowless = Join-Path $shellDirectory 'runtime\python\pythonw.exe'
    $entry = Join-Path $shellDirectory 'app\tools\launch_firelapse.py'
    $launchArguments = '-B -X utf8 "' + $entry + '" --background'
    try {
        $icon = Join-Path $installDir 'FireLapse.ico'
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'FireLapse.ico') -Destination $icon -Force
        $shellIcon = Join-Path $shellDirectory 'FireLapse.ico'
        $desktop = [Environment]::GetFolderPath('DesktopDirectory')
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path $desktop 'FireLapse.lnk'))
        $shortcut.TargetPath = $windowless
        $shortcut.Arguments = $launchArguments
        $shortcut.WorkingDirectory = $shellDirectory
        $shortcut.Description = 'FireLapse - compartment fire timeline'
        $shortcut.IconLocation = "$shellIcon,0"
        $shortcut.Save()
    }
    catch { Write-Warning "Could not create the desktop shortcut. $($_.Exception.Message)" }

    Start-Process -FilePath $windowless -ArgumentList $launchArguments -WorkingDirectory $shellDirectory -WindowStyle Hidden
    exit 0
}
catch {
    [Console]::Error.WriteLine("FireLapse setup failed. $($_.Exception.Message)")
    exit 1
}
