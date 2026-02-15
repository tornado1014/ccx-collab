# Pipeline Runner (Windows)
# Executes pipeline modes:
# - full: validate → plan → split → implement → merge → verify → review → retrospect
# - implement-only: validate → plan → split → implement → merge
# Usage: .\pipeline-runner.ps1 -Task <task.json> -WorkId <work_id> [-ResultsDir <dir>] [-Mode <full|implement-only>]

param(
    [Parameter(Mandatory=$true)]
    [string]$Task,
    [string]$WorkId = "",
    [string]$ResultsDir = "agent\results",
    [ValidateSet("full", "implement-only")]
    [string]$Mode = "full"
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Orchestrate = Join-Path $ScriptDir "orchestrate.py"

if (-not (Test-Path $Task)) {
    Write-Error "Task file not found: $Task"
    exit 1
}

if (-not $WorkId) {
    $WorkId = python3 -c @"
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('$Task').read_bytes()).hexdigest()[:12])
"@
}

$ValidationPath = Join-Path $ResultsDir "validation_$WorkId.json"
$PlanPath = Join-Path $ResultsDir "plan_$WorkId.json"
$DispatchPath = Join-Path $ResultsDir "dispatch_$WorkId.json"
$DispatchMatrixPath = Join-Path $ResultsDir "dispatch_$WorkId.matrix.json"
$ImplementPath = Join-Path $ResultsDir "implement_$WorkId.json"
$VerifyPath = Join-Path $ResultsDir "verify_${WorkId}_windows.json"
$ReviewPath = Join-Path $ResultsDir "review_$WorkId.json"
$RetrospectPath = Join-Path $ResultsDir "retrospect_$WorkId.json"

$ClaudeWrapper = if ($env:CLAUDE_CODE_CMD) { $env:CLAUDE_CODE_CMD } else { Join-Path $ScriptDir "claude-wrapper.ps1" }
$CodexWrapper = if ($env:CODEX_CLI_CMD) { $env:CODEX_CLI_CMD } else { Join-Path $ScriptDir "codex-wrapper.ps1" }

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

function Invoke-Stage {
    param(
        [string]$Stage,
        [scriptblock]$Action
    )
    Write-Host "[$Stage]"
    & $Action
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Error "$Stage failed with exit code $exitCode"
        exit $exitCode
    }
}

function Require-Output {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Error "Expected output file not found: $Path"
        exit 1
    }
}

function Require-OutputJson {
    param(
        [string]$Path,
        [string[]]$RequiredKeys
    )
    Require-Output -Path $Path

    $keysArg = if ($RequiredKeys) { ($RequiredKeys -join ",") } else { "" }
    & python3 - $Path $keysArg @'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
required = [item.strip() for item in sys.argv[2].split(",") if item.strip()]

with path.open("r", encoding="utf-8") as f:
    payload = json.load(f)

if not isinstance(payload, dict):
    raise SystemExit(f"ERROR: {path} is not a JSON object")

missing = [key for key in required if key not in payload]
if missing:
    raise SystemExit(f"ERROR: {path} missing required fields: {', '.join(missing)}")
'@
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Invalid JSON output: $Path"
        exit 1
    }
}

Write-Host "=== Pipeline Runner ==="
Write-Host "Task: $Task"
Write-Host "Work ID: $WorkId"
Write-Host "Mode: $Mode"
Write-Host "Results: $ResultsDir"
Write-Host ""

Write-Host "[1/7] Validating task..."
Invoke-Stage -Stage "validate-task" -Action {
    & python3 $Orchestrate validate-task --task $Task --work-id $WorkId --out $ValidationPath
}
Require-OutputJson -Path $ValidationPath -RequiredKeys @("status")

Write-Host "[2/7] Planning (Claude)..."
Invoke-Stage -Stage "plan" -Action {
    $env:CLAUDE_CODE_CMD = $ClaudeWrapper
    & python3 $Orchestrate run-plan --task $Task --work-id $WorkId --out $PlanPath
}
Require-OutputJson -Path $PlanPath -RequiredKeys @("status")

Write-Host "[3/7] Splitting task..."
Invoke-Stage -Stage "split-task" -Action {
    & python3 $Orchestrate split-task --task $Task --plan $PlanPath --out $DispatchPath --matrix-output $DispatchMatrixPath
}
Require-OutputJson -Path $DispatchPath -RequiredKeys @("subtasks")

Write-Host "[4/7] Implementing subtasks (parallel)..."
$SubtaskData = python3 - "$DispatchPath" @"
import json
import pathlib
import sys

dispatch = json.loads(pathlib.Path(sys.argv[1]).read_text())
for st in dispatch.get('subtasks', []):
    role = st.get('role', st.get('owner', 'builder'))
    if role == 'claude':
        role = 'architect'
    elif role == 'codex':
        role = 'builder'
    print(f\"{st['subtask_id']}|{role}\")
"@

$jobs = @()
foreach ($line in ($SubtaskData -split "`r?`n")) {
    if (-not $line.Trim()) { continue }
    $parts = $line.Trim().Split('|')
    $subtaskId = $parts[0]
    $role = $parts[1]

    Write-Host "  -> $subtaskId (role=$role)"

    $jobs += Start-Job -ScriptBlock {
        param($sd, $task, $dispatchPath, $wid, $subtaskId, $outDir, $role, $claudeWrapper, $codexWrapper)
        if ($role -eq "architect") {
            $env:CLAUDE_CODE_CMD = $claudeWrapper
            $env:CODEX_CLI_CMD = ""
        } else {
            $env:CODEX_CLI_CMD = $codexWrapper
            $env:CLAUDE_CODE_CMD = ""
        }

        & python3 "$sd\orchestrate.py" run-implement `
            --task $task `
            --dispatch $dispatchPath `
            --subtask-id $subtaskId `
            --work-id $wid `
            --out "$outDir\implement_${wid}_${subtaskId}.json"
        if ($LASTEXITCODE -ne 0) {
            throw "run-implement failed for subtask $subtaskId with exit $LASTEXITCODE"
        }
    } -ArgumentList $ScriptDir, $Task, $DispatchPath, $WorkId, $subtaskId, $ResultsDir, $role, $ClaudeWrapper, $CodexWrapper
}

if ($jobs.Count -gt 0) {
    $failedImpl = 0
    $jobs | Wait-Job | Out-Null
    foreach ($job in $jobs) {
        if ($job.State -ne "Completed") {
            $failedImpl += 1
            Write-Error "Implementation job failed: $($job.Id) state=$($job.State)"
            $job.ChildJobs | ForEach-Object { $_.Error | ForEach-Object { Write-Error $_ } } | Out-Null
        }
        Receive-Job $job -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $job
    }
    if ($failedImpl -gt 0) {
        Write-Error "$failedImpl implementation job(s) failed."
        exit 1
    }
}

Write-Host "[5/7] Merging results..."
Invoke-Stage -Stage "merge-results" -Action {
    & python3 $Orchestrate merge-results --work-id $WorkId --kind implement --input "$ResultsDir\implement_${WorkId}_*.json" --dispatch $DispatchPath --out $ImplementPath
}
Require-OutputJson -Path $ImplementPath -RequiredKeys @("status")

if ($Mode -eq "implement-only") {
    Write-Host "[6/7] implement-only mode complete."
    Write-Host ""
    Write-Host "=== Pipeline Complete ==="
    Write-Host "Implement: $ImplementPath"
    exit 0
}

Write-Host "[6/7] Verifying..."
Invoke-Stage -Stage "verify" -Action {
    & python3 $Orchestrate run-verify --work-id $WorkId --platform "windows" --out $VerifyPath
}
Require-OutputJson -Path $VerifyPath -RequiredKeys @("status")

Write-Host "[7/7] Reviewing and generating retrospective..."
Invoke-Stage -Stage "review" -Action {
    & python3 $Orchestrate run-review --work-id $WorkId --plan $PlanPath --implement $ImplementPath --verify $VerifyPath --out $ReviewPath
}
Require-OutputJson -Path $ReviewPath -RequiredKeys @("status","go_no_go")

Invoke-Stage -Stage "retrospect" -Action {
    & python3 $Orchestrate run-retrospect --work-id $WorkId --review $ReviewPath --out $RetrospectPath
}
Require-OutputJson -Path $RetrospectPath -RequiredKeys @("status")

Write-Host ""
Write-Host "=== Pipeline Complete ==="
Write-Host "Review: $ReviewPath"
Write-Host "Retrospective: $RetrospectPath"
