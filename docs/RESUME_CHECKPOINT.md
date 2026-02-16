# Pipeline Resume & Checkpoint Guide

ccx-collab's pipeline supports resuming from the last successful stage, saving time when failures occur mid-pipeline. Instead of restarting from scratch, you pick up right where things broke.

---

## Table of Contents

- [How It Works](#how-it-works)
  - [Stage Result Files](#stage-result-files)
  - [Completion Detection](#completion-detection)
  - [Resume Logic](#resume-logic)
- [Scenario 1: Resume After Failure](#scenario-1-resume-after-failure)
- [Scenario 2: Force Re-run a Specific Stage](#scenario-2-force-re-run-a-specific-stage)
- [Scenario 3: Incremental Development](#scenario-3-incremental-development)
- [Scenario 4: Check Pipeline Status](#scenario-4-check-pipeline-status)
- [Scenario 5: Clean Slate](#scenario-5-clean-slate)
- [Tips](#tips)
- [Troubleshooting](#troubleshooting)
- [Technical Reference](#technical-reference)

---

## How It Works

### Stage Result Files

Each pipeline stage writes a JSON result file to the results directory. The file names follow a predictable pattern based on the stage and work ID:

| Stage      | Result File Pattern                    | Notes                                  |
|------------|----------------------------------------|----------------------------------------|
| validate   | `validation_{work_id}.json`            | Prefix is `validation`, not `validate` |
| plan       | `plan_{work_id}.json`                  |                                        |
| split      | `dispatch_{work_id}.json`              | Prefix is `dispatch`, not `split`      |
| implement  | `implement_{work_id}.json`             | Merged result from all subtasks        |
| merge      | `implement_{work_id}.json`             | Shares prefix with implement stage     |
| verify     | `verify_{work_id}_{platform}.json`     | Platform-specific (macos, linux, etc.) |
| review     | `review_{work_id}.json`               |                                        |
| retrospect | `retrospect_{work_id}.json`            | Always runs after review; not skipped  |

All files are stored in the results directory, which defaults to `agent/results/`.

### Completion Detection

A stage is considered **complete** when its result file:

1. Exists in the results directory
2. Contains valid JSON
3. Has a top-level `"status"` field with one of these values:
   - `"passed"`
   - `"completed"`
   - `"ready"`
   - `"done"`

Any other status value (such as `"failed"` or `"error"`) means the stage is **not** complete, and resume will re-run it.

### Resume Logic

When `--resume` is passed to `ccx-collab run`, the pipeline scans result files **sequentially** from the first stage. It skips stages that have completed result files, stopping as soon as it encounters an incomplete stage. From that point onward, all stages run normally.

This sequential approach is deliberate: later stages depend on the output of earlier stages, so skipping stage 3 but running stage 4 would produce incorrect results.

---

## Scenario 1: Resume After Failure

Your pipeline fails at the verify stage due to a test error.

### Initial run -- fails at verify

```bash
ccx-collab run --task agent/tasks/my-feature.task.json --work-id proj-001
```

Output:

```
=== Pipeline Runner ===
Task:    agent/tasks/my-feature.task.json
Work ID: proj-001
Mode:    full
Results: agent/results

[1/7] Validating task...
[2/7] Planning (Claude)...
[3/7] Splitting task...
[4/7] Implementing subtasks...
  -> proj-001-S01 (role=builder)
  -> proj-001-S02 (role=architect)
[5/7] Merging results...
[6/7] Verifying...
ERROR: Stage Verifying failed (exit code 1)
```

At this point, result files exist for stages 1 through 5 in `agent/results/`.

### Fix the issue and resume

```bash
# Fix whatever caused verification to fail (test code, config, etc.)

# Resume from where it left off
ccx-collab run --task agent/tasks/my-feature.task.json --work-id proj-001 --resume
```

Output:

```
=== Pipeline Runner ===
Task:    agent/tasks/my-feature.task.json
Work ID: proj-001
Mode:    full
Results: agent/results
Resume:  enabled
Skipping: implement, merge, plan, split, validate

[1/7] Validating task -- skipped (already completed)
[2/7] Planning (Claude) -- skipped (already completed)
[3/7] Splitting task -- skipped (already completed)
[4/7] Implementing subtasks -- skipped (already completed)
[5/7] Merging results -- skipped (already completed)
[6/7] Verifying...
[7/7] Reviewing & retrospective...

=== Pipeline Complete ===
Review:        agent/results/review_proj-001.json
Retrospective: agent/results/retrospect_proj-001.json
```

Stages 1 through 5 were skipped because their result files existed with passing status. Only verify, review, and retrospect ran.

---

## Scenario 2: Force Re-run a Specific Stage

You updated your task definition and want to re-run the plan stage, even though it already has a passing result file.

```bash
ccx-collab run \
  --task agent/tasks/my-feature.task.json \
  --work-id proj-001 \
  --resume \
  --force-stage plan
```

Output:

```
=== Pipeline Runner ===
Task:    agent/tasks/my-feature.task.json
Work ID: proj-001
Mode:    full
Results: agent/results
Resume:  enabled
Skipping: validate
Force re-run: plan

[1/7] Validating task -- skipped (already completed)
[2/7] Planning (Claude)...
[3/7] Splitting task...
[4/7] Implementing subtasks...
  -> proj-001-S01 (role=builder)
[5/7] Merging results...
[6/7] Verifying...
[7/7] Reviewing & retrospective...

=== Pipeline Complete ===
```

**What happened:** Only validate (stage 1, before the forced stage) was skipped. Plan (the forced stage) and everything downstream of it ran fresh.

### Why downstream stages re-run

`--force-stage` re-runs the specified stage **and all stages after it**. This is because each stage produces output that feeds into the next. If you re-plan, the split changes, the implementation changes, and so on. Skipping downstream stages after a forced re-run would produce inconsistent results.

### Available force targets

You can force any of these stages: `validate`, `plan`, `split`, `implement`, `merge`, `verify`, `review`.

```bash
# Force re-run from split onward
ccx-collab run --task my-task.json --work-id proj-001 --resume --force-stage split

# Force re-run only verify and review
ccx-collab run --task my-task.json --work-id proj-001 --resume --force-stage verify
```

---

## Scenario 3: Incremental Development

Build your pipeline output step by step, reviewing intermediate results before proceeding.

### Step 1: Validate and plan only

```bash
# Run validation
ccx-collab validate \
  --task agent/tasks/my-feature.task.json \
  --work-id proj-001 \
  --out agent/results/validation_proj-001.json

# Review the validation result, then plan
ccx-collab plan \
  --task agent/tasks/my-feature.task.json \
  --work-id proj-001 \
  --out agent/results/plan_proj-001.json
```

### Step 2: Inspect the plan

```bash
# Check what the pipeline sees so far
ccx-collab status --work-id proj-001
```

Output:

```
        Pipeline Status: proj-001
+------------+------------------------------+---------+--------+
| Stage      | File                         | Status  | Result |
+------------+------------------------------+---------+--------+
| validate   | validation_proj-001.json     | done    | passed |
| plan       | plan_proj-001.json           | done    | passed |
| split      | dispatch_proj-001.json       | missing |        |
| implement  | implement_proj-001.json      | missing |        |
| verify     | verify_proj-001_macos.json   | missing |        |
| review     | review_proj-001.json         | missing |        |
| retrospect | retrospect_proj-001.json     | missing |        |
+------------+------------------------------+---------+--------+
```

### Step 3: Run the rest with resume

Once you are satisfied with the plan, run the full pipeline. Resume detects the completed stages and picks up from split:

```bash
ccx-collab run \
  --task agent/tasks/my-feature.task.json \
  --work-id proj-001 \
  --resume
```

Validate and plan are skipped; split through retrospect run normally.

---

## Scenario 4: Check Pipeline Status

The `status` command gives you a quick overview of which stages are complete for a given work ID.

```bash
ccx-collab status --work-id proj-001
```

```
        Pipeline Status: proj-001
+------------+------------------------------+---------+-----------+
| Stage      | File                         | Status  | Result    |
+------------+------------------------------+---------+-----------+
| validate   | validation_proj-001.json     | done    | passed    |
| plan       | plan_proj-001.json           | done    | completed |
| split      | dispatch_proj-001.json       | done    | passed    |
| implement  | implement_proj-001.json      | missing |           |
| verify     | verify_proj-001_macos.json   | missing |           |
| review     | review_proj-001.json         | missing |           |
| retrospect | retrospect_proj-001.json     | missing |           |
+------------+------------------------------+---------+-----------+
```

The **Status** column shows `done` (file exists and is parseable) or `missing` (no file found). The **Result** column shows the value of the `"status"` field inside the JSON file.

### Custom results directory

If your results are stored somewhere other than `agent/results/`:

```bash
ccx-collab status --work-id proj-001 --results-dir output/my-results
```

---

## Scenario 5: Clean Slate

Sometimes you want to start over completely. There are several ways to do this.

### Option A: Run without --resume

Simply omit `--resume`. The pipeline runs all stages from scratch regardless of existing result files:

```bash
ccx-collab run --task agent/tasks/my-feature.task.json --work-id proj-001
```

Existing result files will be overwritten as each stage completes.

### Option B: Delete specific result files

Remove the result file for the stage you want to re-run. Resume will detect the gap and re-run from that point:

```bash
# Remove the plan result to force re-plan and everything after it
rm agent/results/plan_proj-001.json

ccx-collab run --task agent/tasks/my-feature.task.json --work-id proj-001 --resume
```

### Option C: Use cleanup

The `cleanup` command removes old result files based on retention period:

```bash
# Preview what would be deleted
ccx-collab cleanup --dry-run --retention-days 0

# Delete all result files (retention 0 days)
ccx-collab cleanup --retention-days 0
```

---

## Tips

### Always use a consistent --work-id

The work ID is the key that links result files across stages. If you omit `--work-id`, ccx-collab auto-generates one from the SHA-256 hash of the task file content. This means:

- Changing the task file content changes the work ID
- You lose the ability to resume from previous results
- You cannot easily check status

For any serious pipeline run, always specify `--work-id` explicitly:

```bash
ccx-collab run --task my-task.json --work-id FEAT-042
```

### Result files are your checkpoints

The result JSON files in `agent/results/` are the checkpoint mechanism. There is no separate checkpoint database or state file. This makes the system transparent and easy to debug -- you can read, edit, or delete individual result files to control pipeline behavior.

### Combine with simulation mode

Test your resume flow without making real CLI calls:

```bash
# Initial simulated run
ccx-collab --simulate run --task my-task.json --work-id test-001

# Check status
ccx-collab status --work-id test-001

# Resume (still simulated)
ccx-collab --simulate run --task my-task.json --work-id test-001 --resume
```

### Retrospect always runs

The retrospect stage is not independently skippable. It runs after every successful review, even during a resumed pipeline. This ensures you always get an up-to-date retrospective analysis.

### Use verbose mode for debugging

Add `-v` to see exactly which files the resume logic finds and which stages it decides to skip:

```bash
ccx-collab -v run --task my-task.json --work-id proj-001 --resume
```

This outputs DEBUG-level logs showing:

- Which glob patterns are searched
- Which result files are found
- What status values are read
- Which stages are marked as skippable

---

## Troubleshooting

### Resume skips nothing

**Symptom:** You pass `--resume` but all stages run from the beginning.

**Cause:** The first stage (validate) has no completed result file, or its result file does not contain a recognized status value. Resume scans sequentially and stops skipping at the first incomplete stage.

**Fix:** Check that `agent/results/validation_{work_id}.json` exists and contains `"status": "passed"` (or "completed", "ready", "done"):

```bash
cat agent/results/validation_proj-001.json | python3 -m json.tool | grep status
```

### Resume skips too much

**Symptom:** A stage you expected to re-run was skipped.

**Cause:** Its result file exists and has a passing status.

**Fix:** Delete the result file for the stage you want to re-run, or use `--force-stage`:

```bash
# Option 1: Delete the file
rm agent/results/plan_proj-001.json

# Option 2: Force re-run
ccx-collab run --task my-task.json --work-id proj-001 --resume --force-stage plan
```

### --force-stage has no effect

**Symptom:** You pass `--force-stage` but the stage is not re-run.

**Cause:** `--force-stage` requires `--resume`. Without `--resume`, the pipeline runs all stages from scratch anyway, so `--force-stage` has no meaning.

**Fix:** Always combine the two flags:

```bash
# Correct
ccx-collab run --task my-task.json --work-id proj-001 --resume --force-stage verify

# Incorrect (--force-stage is ignored because --resume is missing)
ccx-collab run --task my-task.json --work-id proj-001 --force-stage verify
```

### Wrong work ID causes resume to miss result files

**Symptom:** Resume cannot find any result files even though they exist.

**Cause:** The work ID used in the resume run does not match the one used in the original run. File names include the work ID, so a mismatch means no files are found.

**Fix:** Check the actual file names in `agent/results/` and use the matching work ID:

```bash
ls agent/results/*.json
# If you see: validation_abc123def456.json
# Then use: --work-id abc123def456
```

### Result file has status "failed" but stage ran successfully

**Symptom:** A stage succeeded on re-run, but resume still wants to re-run it.

**Cause:** The old result file was not overwritten. This can happen if you ran the stage individually without specifying `--out` pointing to the correct result path.

**Fix:** Either delete the old file and re-run, or ensure the output path matches the pattern the pipeline expects:

```bash
# These must match what 'ccx-collab run' produces:
agent/results/validation_{work_id}.json
agent/results/plan_{work_id}.json
agent/results/dispatch_{work_id}.json
agent/results/implement_{work_id}.json
agent/results/verify_{work_id}_{platform}.json
agent/results/review_{work_id}.json
agent/results/retrospect_{work_id}.json
```

---

## Technical Reference

### Resume detection algorithm

The resume logic in `_detect_resume_point()` works as follows:

```
skip_stages = empty set

for each stage in [validate, plan, split, implement, merge, verify, review]:
    if force_stage is set AND current stage index >= force_stage index:
        stop (do not skip this stage or any after it)

    if result file exists with passing status:
        add stage to skip_stages
    else:
        stop (do not skip this stage or any after it)

return skip_stages
```

Key properties:

1. **Sequential scanning** -- stages are checked in order; the first incomplete stage stops the scan
2. **Force boundary** -- `--force-stage` sets a hard boundary; nothing at or after that stage is skipped
3. **Glob matching** -- result files are matched with `{prefix}_{work_id}*.json`, allowing for platform suffixes and other variations

### Stage name to file prefix mapping

The pipeline uses different prefixes for some stage names:

| Stage Name | File Prefix  |
|------------|-------------|
| validate   | `validation` |
| plan       | `plan`       |
| split      | `dispatch`   |
| implement  | `implement`  |
| merge      | `implement`  |
| verify     | `verify`     |
| review     | `review`     |

Note that `merge` and `implement` share the same prefix. The merged result overwrites the individual implementation result, so this works correctly in practice.
