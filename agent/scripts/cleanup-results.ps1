# Cleanup Results Script (Windows)
# Removes old JSON result files from the results directory.
# Usage: .\cleanup-results.ps1 [-ResultsDir <dir>] [-RetentionDays <n>] [-DryRun]

param(
    [string]$ResultsDir = "agent\results",
    [int]$RetentionDays = 30,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ResultsDir -PathType Container)) {
    Write-Error "Results directory does not exist: $ResultsDir"
    exit 1
}

if ($RetentionDays -lt 1) {
    Write-Error "--retention-days must be a positive integer, got: $RetentionDays"
    exit 1
}

Write-Host "=== Results Cleanup ==="
Write-Host "Directory:      $ResultsDir"
Write-Host "Retention days: $RetentionDays"
if ($DryRun) {
    Write-Host "Mode:           DRY RUN (no files will be deleted)"
} else {
    Write-Host "Mode:           LIVE"
}
Write-Host ""

$cutoffDate = (Get-Date).AddDays(-$RetentionDays)
$deletedCount = 0
$freedBytes = 0

# Find JSON files older than retention days (only files, never directories)
$jsonFiles = Get-ChildItem -Path $ResultsDir -Filter "*.json" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoffDate }

foreach ($file in $jsonFiles) {
    $fileSize = $file.Length

    if ($DryRun) {
        Write-Host "[dry-run] Would delete: $($file.FullName) ($fileSize bytes)"
    } else {
        Remove-Item -Path $file.FullName -Force
        Write-Host "Deleted: $($file.FullName)"
    }

    $deletedCount++
    $freedBytes += $fileSize
}

# Format freed space for human readability
if ($freedBytes -ge 1MB) {
    $freedDisplay = "{0:N2} MB" -f ($freedBytes / 1MB)
} elseif ($freedBytes -ge 1KB) {
    $freedDisplay = "{0:N2} KB" -f ($freedBytes / 1KB)
} else {
    $freedDisplay = "$freedBytes bytes"
}

Write-Host ""
Write-Host "=== Summary ==="
if ($DryRun) {
    Write-Host "Files that would be deleted: $deletedCount"
    Write-Host "Space that would be freed:   $freedDisplay"
} else {
    Write-Host "Files deleted: $deletedCount"
    Write-Host "Space freed:   $freedDisplay"
}
