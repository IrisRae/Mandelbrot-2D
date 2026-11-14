param([ValidateSet('Debug','Release')][string]$Configuration='Release',[switch]$Run,[switch]$Verify)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$vswhere="${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsRoot=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$vsRoot) { throw 'Visual Studio C++ tools are required.' }
$cmake=Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
Push-Location -LiteralPath $projectRoot
try {
    $configureArgs=@('--preset','vs2026')
    $cache=Join-Path $projectRoot 'build\vs2026\CMakeCache.txt'
    if(Test-Path -LiteralPath $cache) {
        $line=Get-Content -LiteralPath $cache | Where-Object { $_ -match '^CMAKE_HOME_DIRECTORY:INTERNAL=' }
        if($line) {
            $cachedPath=$line.Substring($line.IndexOf('=')+1).Replace('/','\').TrimEnd('\')
            if($cachedPath -ne $projectRoot.TrimEnd('\')) { $configureArgs+='--fresh' }
        }
    }
    & $cmake @configureArgs
    if($LASTEXITCODE -ne 0) { throw 'Configure failed.' }
    & $cmake --build --preset $Configuration.ToLowerInvariant() --parallel 4
    if($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    $exe=Join-Path $projectRoot "build\vs2026\$Configuration\mandelbulb.exe"
    if($Verify) { & $exe --verify; if($LASTEXITCODE -ne 0){throw 'GPU verification failed.'} }
    elseif($Run) { & $exe; if($LASTEXITCODE -ne 0){throw 'Application failed.'} }
} finally { Pop-Location }
