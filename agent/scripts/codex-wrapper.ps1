# Codex CLI Wrapper (Windows)
# Reads JSON payload from stdin, runs Codex CLI, outputs JSON envelope to stdout.

$ErrorActionPreference = "Stop"
$envelopeEmitted = $false
$stderrFile = $null

function New-Envelope {
    param(
        [string]$Status,
        [int]$ExitCode,
        [string]$Stdout,
        [string]$Stderr,
        [hashtable]$Result
    )

    @{
        status    = $Status
        exit_code = $ExitCode
        stdout    = $Stdout
        stderr    = $Stderr
        result    = $Result
    } | ConvertTo-Json -Depth 10 -Compress
}

try {
    $payloadText = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($payloadText)) {
        throw "No JSON payload provided on stdin."
    }

    $payload = $payloadText | ConvertFrom-Json -ErrorAction Stop
    $prompt = if ($payload.PSObject.Properties.Name -contains "request" -and $payload.request) {
        $payload.request
    } else {
        "Process the provided task payload and return structured JSON results."
    }

    $stderrFile = [System.IO.Path]::GetTempFileName()
    $exitCode = 0
    $resultText = ""

    try {
        $resultText = & codex --approval-mode full-auto --quiet $prompt 2>$stderrFile
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
    } catch {
        $exitCode = 1
        $resultText = ""
    }

    $stderrText = ""
    if (Test-Path $stderrFile) {
        $stderrText = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
    }

    try {
        $resultObj = $resultText | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    } catch {
        $resultObj = @{}
    }

    $status = if ($exitCode -eq 0) { "passed" } else { "failed" }
    $envelope = New-Envelope -Status $status -ExitCode $exitCode -Stdout ($resultText -join "`n") -Stderr ($stderrText -join "`n") -Result $resultObj
    $envelopeEmitted = $true
    Write-Output $envelope
} catch {
    if (-not $envelopeEmitted) {
        $envelope = New-Envelope -Status "failed" -ExitCode 1 -Stdout "" -Stderr $_.Exception.Message -Result @{}
        Write-Output $envelope
    }
} finally {
    if ($stderrFile -and (Test-Path $stderrFile)) {
        Remove-Item $stderrFile -Force -ErrorAction SilentlyContinue
    }
}
