[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw 'Project .venv\Scripts\python.exe is required to build (not to run the distribution).'
}

& $pythonExe -m pip install --disable-pip-version-check --retries 0 -r (Join-Path $projectRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Build dependency installation failed. Install requirements-build.txt into this .venv from an online PowerShell or an offline wheel folder, then retry.'
}

& $pythonExe (Join-Path $projectRoot 'tools\prepare_model_distribution.py')
if ($LASTEXITCODE -ne 0) { throw 'Offline model resources or license notices are missing. Run the explicit build-time model fetch first.' }

$distribution = Join-Path $projectRoot 'dist\notice_crawling'
$workPath = Join-Path $projectRoot 'build\notice_crawling'
$specPath = Join-Path $projectRoot 'build\windows_spec'
$prefix = $projectRoot.TrimEnd('\') + '\'

# Clean only this application's generated outputs. Validate absolute paths and
# refuse junction/symlink ancestors before any recursive filesystem operation.
foreach ($target in @($distribution, $workPath, $specPath)) {
    $absolute = [IO.Path]::GetFullPath($target)
    if (-not $absolute.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean a path outside the project.'
    }
    $ancestor = $absolute
    while ($ancestor -and $ancestor -ne $projectRoot) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Refusing to clean generated output through a junction/symlink.'
            }
        }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
    if (Test-Path -LiteralPath $absolute) {
        Remove-Item -LiteralPath $absolute -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $specPath -Force | Out-Null

$buildArguments = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', 'notice_crawling', '--noupx', '--contents-directory', '_internal',
    '--distpath', (Join-Path $projectRoot 'dist'), '--workpath', $workPath,
    '--specpath', $specPath, '--paths', $projectRoot,
    '--exclude-module', 'unittest', '--exclude-module', 'tests',
    '--exclude-module', 'tkinter.test',
    '--exclude-module', 'torch', '--exclude-module', 'transformers',
    '--exclude-module', 'huggingface_hub', '--exclude-module', 'hf_xet',
    '--exclude-module', 'onnxruntime.tools', '--exclude-module', 'onnxruntime.quantization',
    '--add-data', ((Join-Path $projectRoot 'resources\models\performance_classifier') + ';models\performance_classifier'),
    (Join-Path $projectRoot 'tools\windows_entry.py')
)
Push-Location -LiteralPath $projectRoot
$previousBuildCache = $env:PYINSTALLER_CONFIG_DIR
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $workPath 'pyinstaller-cache'
    & $pythonExe @buildArguments
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    $executable = Join-Path $distribution 'notice_crawling.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Executable was not generated.' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\windows_README.txt') -Destination (Join-Path $distribution 'README.txt')
    Write-Host "Distribution: $distribution"
    Write-Host 'Distribute the entire folder, including _internal. No user database/cache is bundled.'
} finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousBuildCache
    Pop-Location
}
