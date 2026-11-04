[CmdletBinding()]
param([string]$RunId = [guid]::NewGuid().ToString('N'))
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid test run ID' }
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$exe = Join-Path $project 'dist\notice_crawling\notice_crawling.exe'
$fixture = 'tests/fixtures/performance_enrichment/runtime/final_verification/'
$database = $fixture + 'frozen-' + $RunId + '.db'
$common = '--upload-file ' + $fixture + 'five-rows.xlsx --smoke-db ' + $database +
    ' --smoke-cache ' + $fixture + 'snapshot.json --smoke-base-url https://example.test/ --enrichment-check --management-check'
foreach ($phase in @('import', 'restart')) {
    $arguments = '--upload-smoke-report .run/final-exe-' + $phase + '.json ' + $common
    if ($phase -eq 'restart') { $arguments += ' --verify-only' }
    $process = Start-Process -FilePath $exe -WorkingDirectory $project -WindowStyle Hidden -Wait -PassThru -ArgumentList $arguments
    Write-Output ('FINAL_EXE_' + $phase.ToUpperInvariant() + '_EXIT=' + $process.ExitCode)
    Get-Content -LiteralPath (Join-Path $project ('.run/final-exe-' + $phase + '.json')) -Encoding UTF8
    if ($process.ExitCode -ne 0) { throw ('Frozen ' + $phase + ' verification failed') }
}
