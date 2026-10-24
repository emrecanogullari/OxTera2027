# Build Peter/ingest/cpp with VS 2017 (or later) cl.exe.
# Run from this folder:  powershell -File compile.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $here "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vcvars = $null
if (Test-Path $vswhere) {
    $root = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($root) { $vcvars = Join-Path $root "VC\Auxiliary\Build\vcvars64.bat" }
}
if (-not $vcvars) {
    $fallback = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat"
    if (Test-Path $fallback) { $vcvars = $fallback }
}
if (-not $vcvars -or -not (Test-Path $vcvars)) {
    Write-Error "No Visual Studio C++ tools found. Install the 'Desktop development with C++' workload."
}

$src = Join-Path $here "src"
$out = Join-Path $build "ingest.exe"
$cmd = "`"$vcvars`" && cl /nologo /EHsc /std:c++17 /O2 /W3 /I`"$src`" /Fe:`"$out`" /Fo:`"$build\\`" `"$src\pgn.cpp`" `"$src\main.cpp`""
cmd.exe /c $cmd
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "built $out"
