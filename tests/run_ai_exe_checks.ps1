[CmdletBinding()]
param([string]$RunId = [guid]::NewGuid().ToString('N'))
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid test run ID' }
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$exe = Join-Path $project 'dist\notice_crawling\notice_crawling.exe'
$fixture = 'tests/fixtures/performance_enrichment/runtime/'
$database = $fixture + 'ai-frozen-' + $RunId + '.db'
$common = '--upload-file ' + $fixture + 'ai-upload.xlsx --smoke-db ' + $database +
    ' --smoke-cache ' + $fixture + 'snapshot.json --smoke-base-url https://example.test/ --enrichment-check --management-check'
$first = Start-Process -FilePath $exe -WorkingDirectory $project -WindowStyle Hidden -Wait -PassThru -ArgumentList (
    '--upload-smoke-report .run/ai-exe-import.json ' + $common)
Write-Output ('AI_EXE_EXIT=' + $first.ExitCode)
Get-Content -LiteralPath (Join-Path $project '.run/ai-exe-import.json') -Encoding UTF8
if ($first.ExitCode -ne 0) { throw 'Frozen import test failed' }
$second = Start-Process -FilePath $exe -WorkingDirectory $project -WindowStyle Hidden -Wait -PassThru -ArgumentList (
    '--upload-smoke-report .run/ai-exe-restart.json ' + $common + ' --verify-only')
Write-Output ('AI_RESTART_EXIT=' + $second.ExitCode)
Get-Content -LiteralPath (Join-Path $project '.run/ai-exe-restart.json') -Encoding UTF8
if ($second.ExitCode -ne 0) { throw 'Frozen restart test failed' }
