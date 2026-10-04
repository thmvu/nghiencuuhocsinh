$ErrorActionPreference = 'Stop'
$reviewWorkspace = Split-Path -Parent $PSScriptRoot
$reviewPython = Join-Path $reviewWorkspace '.venv\Scripts\python.exe'
$reviewRunner = Join-Path $PSScriptRoot 'run_foundational_rq2_review_ui.py'
$reviewUrl = 'http://127.0.0.1:9411'
$reviewReady = $false
try {
    $reviewState = Invoke-RestMethod -Uri "$reviewUrl/api/state" -TimeoutSec 2
    $reviewReady = $reviewState.role -eq 'project_author' -and $reviewState.total -eq 40 -and -not $reviewState.demo
} catch { }
if (-not $reviewReady) {
    $reviewLogs = Join-Path $reviewWorkspace 'artifacts\logs\review_ui'
    New-Item -ItemType Directory -Force -Path $reviewLogs | Out-Null
    Start-Process -FilePath $reviewPython -ArgumentList @("`"$reviewRunner`"", '--port', '9411') -WorkingDirectory $reviewWorkspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $reviewLogs 'server_stdout.log') -RedirectStandardError (Join-Path $reviewLogs 'server_stderr.log') | Out-Null
    for ($reviewAttempt = 0; $reviewAttempt -lt 20; $reviewAttempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $reviewState = Invoke-RestMethod -Uri "$reviewUrl/api/state" -TimeoutSec 2
            $reviewReady = $reviewState.role -eq 'project_author' -and $reviewState.total -eq 40 -and -not $reviewState.demo
            if ($reviewReady) { break }
        } catch { }
    }
}
if (-not $reviewReady) { throw 'Chua mo duoc giao dien. Xem artifacts/logs/review_ui/server_stderr.log.' }
Start-Process $reviewUrl
