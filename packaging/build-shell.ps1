param(
    [ValidateSet('Release', 'Debug')]
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDirectory = Join-Path $repoRoot 'shell'
$outputDirectory = Join-Path $repoRoot 'build\shell'
$null = New-Item -ItemType Directory -Force -Path $outputDirectory

$cmake = Get-Command cmake.exe -ErrorAction SilentlyContinue
if (-not $cmake) {
    $cmakeCandidate = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    if (Test-Path -LiteralPath $cmakeCandidate) {
        $cmake = [pscustomobject]@{ Source = $cmakeCandidate }
    }
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$visualStudio = $null
if ($cmake -and (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
    $visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}

if ($visualStudio) {
    $buildDirectory = Join-Path $outputDirectory 'msvc'
    # Let CMake select the installed Visual Studio version on local/CI machines.
    & $cmake.Source -S $sourceDirectory -B $buildDirectory -A x64
    if ($LASTEXITCODE -ne 0) { throw "CMake configure failed (exit $LASTEXITCODE)." }
    & $cmake.Source --build $buildDirectory --config $Configuration --parallel
    if ($LASTEXITCODE -ne 0) { throw "MSVC build failed (exit $LASTEXITCODE)." }
    & (Join-Path (Split-Path $cmake.Source) 'ctest.exe') --test-dir $buildDirectory -C $Configuration --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw 'Native shell selection validation failed.' }
    $builtDll = Join-Path $buildDirectory "$Configuration\TangerineShell.dll"
    Copy-Item -LiteralPath $builtDll -Destination (Join-Path $outputDirectory 'TangerineShell.dll') -Force
} else {
    $compilerPath = 'C:\ProgramData\mingw64\mingw64\bin\g++.exe'
    if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) {
        throw 'No Visual Studio C++ toolchain or configured MinGW compiler found; no tools were installed.'
    }
    $outputPath = Join-Path $outputDirectory 'TangerineShell.dll'
    & $compilerPath -std=c++17 -O2 -Wall -Wextra -Werror -static -shared `
        '-Wl,--no-insert-timestamp' `
        (Join-Path $sourceDirectory 'TangerineShell.cpp') `
        (Join-Path $sourceDirectory 'TangerineShell.def') `
        -o $outputPath -lole32 -lshell32 -luuid -ladvapi32 -luser32
    if ($LASTEXITCODE -ne 0) { throw "MinGW build failed (exit $LASTEXITCODE)." }
    $harness = Join-Path $outputDirectory 'ValidateShell.exe'
    & $compilerPath -std=c++17 -O2 -Wall -Wextra -Werror -static -municode `
        (Join-Path $sourceDirectory 'tests\ValidateShell.cpp') -o $harness -lole32 -lshell32 -luuid -luser32
    if ($LASTEXITCODE -ne 0) { throw 'Native shell validation harness failed to compile.' }
    & $harness $outputPath
    if ($LASTEXITCODE -ne 0) { throw 'Native shell selection validation failed.' }
}

$dll = Join-Path $outputDirectory 'TangerineShell.dll'
if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { throw "Build output missing: $dll" }
Write-Output "SHELL_DLL=$dll"
