# ---------------------------------------------------------------------------
# FilePetal for Windows - one-shot packaging script (no admin required).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -DistDir build\validation-dist -SkipInstaller
#
# Steps:
#   1. ensure PyInstaller is installed for the current Python
#   2. build the onedir/windowed bundle: dist\FilePetal\
#   3. create dist\FilePetal-<version>-windows-x64.zip
#   4. if Inno Setup 6 (ISCC.exe) is available, compile
#      dist\FilePetal-Setup.exe
# ---------------------------------------------------------------------------
#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipInstaller,
    [string]$DistDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DistDir)) {
    $DistDir = Join-Path $RepoRoot "dist"
}
elseif (-not [System.IO.Path]::IsPathRooted($DistDir)) {
    $DistDir = Join-Path $RepoRoot $DistDir
}
$DistDir = [System.IO.Path]::GetFullPath($DistDir)
$OriginalBuildPath = $null
$SpecRel = "packaging\filepetal.spec"
$SpecFile = Join-Path $PSScriptRoot "filepetal.spec"
$IssFile = Join-Path $PSScriptRoot "installer.iss"
$PathsFile = Join-Path $RepoRoot "tangerine\paths.py"
$BundleDir = Join-Path $DistDir "FilePetal"
$BundleExe = Join-Path $BundleDir "FilePetal.exe"

function Get-AppVersion {
    param([Parameter(Mandatory = $true)][string]$PathsFile)
    $pattern = '^\s*APP_VERSION\s*=\s*[''"]\s*([^''"\s]+)'
    $match = Select-String -LiteralPath $PathsFile -Pattern $pattern | Select-Object -First 1
    if (-not $match) {
        throw "Could not read APP_VERSION from $PathsFile"
    }
    return $match.Matches[0].Groups[1].Value
}

function Format-Size {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N1} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N1} KB' -f ($Bytes / 1KB)) }
    return "$Bytes B"
}

function Find-Iscc {
    $candidates = @()
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    }
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $onPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    return $null
}

try {
    $Version = Get-AppVersion -PathsFile $PathsFile
    Write-Host "==> FilePetal for Windows $Version" -ForegroundColor Cyan

    Write-Host "==> [1/4] Checking PyInstaller"
    & $Python -m PyInstaller --version
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install pyinstaller pyinstaller-hooks-contrib
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed with exit code $LASTEXITCODE" }
    }

    Write-Host "==> [2/4] Building frozen bundle (onedir, windowed)"
    & (Join-Path $PSScriptRoot "build-shell.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Native Explorer bridge build failed." }
    try {
        $OriginalBuildPath = $env:PATH
        $WindowsDllDirectories = @(
            (Join-Path $env:SystemRoot "System32"),
            $env:SystemRoot
        )
        $WindowsDllDirectoryKeys = @(
            $WindowsDllDirectories | ForEach-Object { $_.TrimEnd('\') }
        )
        $RemainingBuildPath = @(
            $OriginalBuildPath -split ';' | Where-Object {
                $_ -and $_.TrimEnd('\') -notin $WindowsDllDirectoryKeys
            }
        )
        $env:PATH = (@($WindowsDllDirectories) + $RemainingBuildPath) -join ';'
        Write-Host "    Windows system DLL directories take precedence during analysis."

        Push-Location -LiteralPath $RepoRoot
        if (Test-Path -LiteralPath $BundleDir) {
            Remove-Item -LiteralPath $BundleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        $buildDir = Join-Path $RepoRoot "build\filepetal"
        if (Test-Path -LiteralPath $buildDir) {
            Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        try {
            & $Python -m PyInstaller --noconfirm --clean --distpath $DistDir $SpecRel
            if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($null -ne $OriginalBuildPath) { $env:PATH = $OriginalBuildPath }
    }
    if (-not (Test-Path -LiteralPath $BundleExe)) {
        throw "Expected frozen executable not found: $BundleExe"
    }

    # Ensure bundled tools exist in BundleDir/tools as well
    $RepoTools = Join-Path $RepoRoot "tools"
    $BundleTools = Join-Path $BundleDir "tools"
    if (Test-Path -LiteralPath $RepoTools) {
        if (-not (Test-Path -LiteralPath $BundleTools)) {
            New-Item -ItemType Directory -Path $BundleTools -Force | Out-Null
        }
        Get-ChildItem -LiteralPath $RepoTools | ForEach-Object {
            $dest = Join-Path $BundleTools $_.Name
            if (-not (Test-Path -LiteralPath $dest)) {
                Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
            }
        }
    }

    Write-Host "==> Checking the frozen Qt WebEngine payload"
    $QtWebEngineDir = Join-Path $BundleDir "_internal\PySide6"
    $RequiredWebEngineFiles = @(
        "QtWebEngineProcess.exe",
        "Qt6WebEngineCore.dll",
        "QtWebEngineCore.pyd",
        "resources\icudtl.dat",
        "resources\qtwebengine_resources.pak",
        "resources\v8_context_snapshot.bin",
        "translations\qtwebengine_locales\en-US.pak"
    )
    foreach ($relativePath in $RequiredWebEngineFiles) {
        $requiredPath = Join-Path $QtWebEngineDir $relativePath
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required Qt WebEngine file is missing from the frozen bundle: $requiredPath"
        }
    }
    $helperVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo(
        (Join-Path $QtWebEngineDir "QtWebEngineProcess.exe")
    ).FileVersion
    $coreVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo(
        (Join-Path $QtWebEngineDir "Qt6WebEngineCore.dll")
    ).FileVersion
    if ($helperVersion -and $coreVersion -and $helperVersion -ne $coreVersion) {
        throw "Qt WebEngine helper/DLL versions differ: helper=$helperVersion core=$coreVersion"
    }
    Write-Host ("    Helper and Core DLL: {0}" -f $helperVersion)

    Write-Host "==> Exercising the frozen Qt WebEngine"
    $SmokeProcess = Start-Process -FilePath $BundleExe -ArgumentList "--smoke-webengine" -WindowStyle Hidden -PassThru
    if (-not $SmokeProcess.WaitForExit(30000)) {
        Stop-Process -Id $SmokeProcess.Id -Force
        throw "Frozen Qt WebEngine smoke test timed out."
    }
    $SmokeProcess.Refresh()
    if ($SmokeProcess.ExitCode -ne 0) {
        $SmokeLog = Join-Path $env:TEMP "FilePetal-webengine-smoke.log"
        if (-not (Test-Path -LiteralPath $SmokeLog)) {
            $SmokeLog = Join-Path $env:TEMP "Tangerine-webengine-smoke.log"
        }
        if (Test-Path -LiteralPath $SmokeLog) {
            Get-Content -LiteralPath $SmokeLog
        }
        throw "Frozen Qt WebEngine smoke test failed with exit code $($SmokeProcess.ExitCode)"
    }
    Write-Host "    Qt WebEngine loaded and rendered its local smoke page."

    Write-Host "==> Exercising the frozen image PDF editor, engine and progress card"
    $PdfSmoke = Start-Process -FilePath $BundleExe -ArgumentList "--smoke-image-pdf" -WindowStyle Hidden -PassThru
    if (-not $PdfSmoke.WaitForExit(30000)) {
        Stop-Process -Id $PdfSmoke.Id -Force
        throw "Frozen image PDF smoke test timed out."
    }
    $PdfSmoke.Refresh()
    $PdfSmokeLog = Join-Path $env:TEMP "Tangerine-image-pdf-smoke.json"
    if (Test-Path -LiteralPath $PdfSmokeLog) { Get-Content -LiteralPath $PdfSmokeLog }
    if ($PdfSmoke.ExitCode -ne 0) { throw "Frozen image PDF smoke test failed with exit code $($PdfSmoke.ExitCode)." }
    $PdfReceipt = Get-Content -LiteralPath $PdfSmokeLog -Raw | ConvertFrom-Json
    if (-not $PdfReceipt.ok -or $PdfReceipt.version -ne $Version -or $PdfReceipt.ipc_requests -ne 2) {
        throw 'Frozen PDF validation receipt is incomplete or belongs to another version.'
    }

    Write-Host "==> Exercising the frozen image editors and opt-in batch options"
    $EditorSmoke = Start-Process -FilePath $BundleExe -ArgumentList "--smoke-editors" -WindowStyle Hidden -PassThru
    if (-not $EditorSmoke.WaitForExit(30000)) {
        Stop-Process -Id $EditorSmoke.Id -Force
        throw "Frozen editor smoke test timed out."
    }
    $EditorSmoke.Refresh()
    $EditorReceiptPath = Join-Path $env:TEMP "Tangerine-editors-smoke.json"
    if (Test-Path -LiteralPath $EditorReceiptPath) { Get-Content -LiteralPath $EditorReceiptPath }
    if ($EditorSmoke.ExitCode -ne 0) { throw "Frozen editor smoke test failed with exit code $($EditorSmoke.ExitCode)." }
    $EditorReceipt = Get-Content -LiteralPath $EditorReceiptPath -Raw | ConvertFrom-Json
    if (-not $EditorReceipt.ok -or $EditorReceipt.version -ne $Version) {
        throw 'Frozen editor validation receipt is incomplete or belongs to another version.'
    }

    Write-Host "==> [3/4] Creating portable archive"
    $PortableZip = Join-Path $DistDir "FilePetal-$Version-windows-x64.zip"
    if (Test-Path -LiteralPath $PortableZip) { Remove-Item -LiteralPath $PortableZip -Force }
    Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $PortableZip -CompressionLevel Optimal
    if (-not (Test-Path -LiteralPath $PortableZip)) {
        throw "Portable archive was not created: $PortableZip"
    }

    $Installer = Join-Path $DistDir "FilePetal-Setup.exe"
    $Iscc = $null
    if (-not $SkipInstaller) {
        Write-Host "==> [4/4] Building installer with Inno Setup 6"
        $Iscc = Find-Iscc
    }

    if ($SkipInstaller) {
        Write-Warning "Installer build skipped (-SkipInstaller)."
    }
    elseif (-not $Iscc) {
        Write-Warning "ISCC.exe (Inno Setup 6) not found - installer not built."
        Write-Warning "Install it with: winget install --id JRSoftware.InnoSetup -e"
        Write-Warning "Then re-run: ISCC.exe /DAPPVER=$Version `"$IssFile`""
    }
    else {
        Write-Host "    Using: $Iscc"
        if (Test-Path -LiteralPath $Installer) { Remove-Item -LiteralPath $Installer -Force }
        & $Iscc "/DAPPVER=$Version" "/DBUNDLEDIR=$BundleDir" "/DOUTPUTDIR=$DistDir" $IssFile
        if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }
        if (-not (Test-Path -LiteralPath $Installer)) {
            throw "Setup executable was not created: $Installer"
        }
    }

    Write-Host ""
    Write-Host "================= FilePetal build summary =================" -ForegroundColor Cyan
    Write-Host ("Version       : {0}" -f $Version)
    Write-Host ("Frozen bundle : {0}" -f $BundleDir)
    $exeItem = Get-Item -LiteralPath $BundleExe
    Write-Host ("  FilePetal.exe : {0}" -f (Format-Size $exeItem.Length))
    $zipItem = Get-Item -LiteralPath $PortableZip
    Write-Host ("Portable zip  : {0} ({1})" -f $PortableZip, (Format-Size $zipItem.Length))
    if (Test-Path -LiteralPath $Installer) {
        $setupItem = Get-Item -LiteralPath $Installer
        Write-Host ("Installer     : {0} ({1})" -f $Installer, (Format-Size $setupItem.Length))
    }
    else {
        Write-Host "Installer     : not built (ISCC.exe unavailable or skipped)"
    }
    Write-Host "===========================================================" -ForegroundColor Cyan
}
catch {
    Write-Host ""
    Write-Host ("BUILD FAILED: {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}

exit 0
