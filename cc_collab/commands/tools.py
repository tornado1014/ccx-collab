"""Utility commands: health, cleanup, init."""
import click
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_single_health_check(out: str = "") -> dict:
    """Run a single health check and capture structured result.

    Returns a dict with 'rc' (int) and 'data' (parsed JSON from health check).
    """
    from cc_collab.bridge import run_health_check

    # Capture stdout from orchestrate's print() calls
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()
    try:
        rc = run_health_check(out=out)
    finally:
        sys.stdout = old_stdout

    raw = captured.getvalue().strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        data = {"raw_output": raw}

    return {"rc": rc, "data": data}


def _format_json_result(check_data: dict) -> dict:
    """Build structured JSON output for a single health check."""
    ts = datetime.now(timezone.utc).isoformat()
    status_value = check_data.get("status", "unknown")
    # Normalize: treat anything other than "healthy" as "unhealthy"
    # but preserve "skipped" for simulation mode
    if status_value not in ("healthy", "skipped"):
        status_value = "unhealthy"
    return {
        "timestamp": ts,
        "status": status_value,
        "checks": check_data.get("agents", check_data),
    }


@click.command()
@click.option("--out", default="", help="Output path for health check results")
@click.option("--continuous", is_flag=True, help="Run health checks in a loop until interrupted")
@click.option("--interval", default=60, type=int, help="Seconds between checks in continuous mode (default: 60)")
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON for machine parsing")
@click.pass_context
def health(ctx, out, continuous, interval, json_output):
    """Check CLI tool health (Claude Code, Codex CLI)."""
    from cc_collab.output import print_stage_result

    logger.debug("Health check starting: out=%s, continuous=%s, interval=%d, json=%s",
                 out, continuous, interval, json_output)

    if continuous:
        total_checks = 0
        total_passes = 0
        total_failures = 0

        try:
            while True:
                result = _run_single_health_check(out=out)
                rc = result["rc"]
                total_checks += 1
                if rc == 0:
                    total_passes += 1
                else:
                    total_failures += 1

                ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                if json_output:
                    structured = _format_json_result(result["data"])
                    click.echo(json.dumps(structured))
                else:
                    status_label = "HEALTHY" if rc == 0 else "UNHEALTHY"
                    click.echo(f"[{ts_str}] Health check: {status_label}")
                    # Print captured health check details
                    raw_data = result["data"]
                    if isinstance(raw_data, dict) and "raw_output" not in raw_data:
                        click.echo(json.dumps(raw_data, indent=2))
                    elif isinstance(raw_data, dict) and raw_data.get("raw_output"):
                        click.echo(raw_data["raw_output"])
                    print_stage_result("health", rc, out)

                time.sleep(interval)
        except KeyboardInterrupt:
            click.echo("")
            click.echo(f"--- Continuous Health Check Summary ---")
            click.echo(f"Total checks: {total_checks}")
            click.echo(f"Passes:       {total_passes}")
            click.echo(f"Failures:     {total_failures}")
            # Exit cleanly
            return

    else:
        result = _run_single_health_check(out=out)
        rc = result["rc"]

        if json_output:
            structured = _format_json_result(result["data"])
            click.echo(json.dumps(structured))
        else:
            # Print the captured health check output (preserves "skipped" etc.)
            raw_data = result["data"]
            if isinstance(raw_data, dict) and "raw_output" not in raw_data:
                click.echo(json.dumps(raw_data, indent=2))
            elif isinstance(raw_data, dict) and raw_data.get("raw_output"):
                click.echo(raw_data["raw_output"])
            print_stage_result("health", rc, out)

        if rc != 0:
            sys.exit(rc)


@click.command()
@click.option("--results-dir", default="agent/results", help="Results directory")
@click.option("--retention-days", default=30, type=int, help="Keep files newer than N days")
@click.option("--dry-run", is_flag=True, help="Preview deletions without executing")
@click.pass_context
def cleanup(ctx, results_dir, retention_days, dry_run):
    """Clean up old pipeline result files."""
    from cc_collab.output import console, print_error, print_success

    logger.debug("Cleanup starting: results_dir=%s, retention_days=%d, dry_run=%s",
                 results_dir, retention_days, dry_run)

    results = Path(results_dir)
    if not results.is_dir():
        print_error(f"Results directory does not exist: {results_dir}")
        sys.exit(1)

    if retention_days < 1:
        print_error(f"--retention-days must be a positive integer, got: {retention_days}")
        sys.exit(1)

    cutoff = time.time() - (retention_days * 86400)
    deleted_count = 0
    freed_bytes = 0

    console.print(f"[bold]=== Results Cleanup ===[/bold]")
    console.print(f"Directory:      {results_dir}")
    console.print(f"Retention days: {retention_days}")
    console.print(f"Mode:           {'DRY RUN' if dry_run else 'LIVE'}")
    console.print()

    json_files = sorted(results.glob("*.json"))
    logger.debug("Scanning %d JSON file(s) in %s", len(json_files), results_dir)

    for f in json_files:
        if not f.is_file():
            continue
        if f.stat().st_mtime >= cutoff:
            logger.debug("Keeping (within retention): %s", f.name)
            continue

        file_size = f.stat().st_size
        if dry_run:
            logger.debug("Would delete (dry-run): %s (%d bytes)", f.name, file_size)
            console.print(f"[dim][dry-run][/dim] Would delete: {f} ({file_size} bytes)")
        else:
            logger.debug("Deleting: %s (%d bytes)", f.name, file_size)
            f.unlink()
            console.print(f"Deleted: {f}")

        deleted_count += 1
        freed_bytes += file_size

    # Format freed space
    if freed_bytes >= 1048576:
        freed_display = f"{freed_bytes / 1048576:.2f} MB"
    elif freed_bytes >= 1024:
        freed_display = f"{freed_bytes / 1024:.2f} KB"
    else:
        freed_display = f"{freed_bytes} bytes"

    logger.debug("Cleanup complete: %d file(s), %s freed", deleted_count, freed_display)

    console.print()
    console.print("[bold]=== Summary ===[/bold]")
    if dry_run:
        console.print(f"Files that would be deleted: {deleted_count}")
        console.print(f"Space that would be freed:   {freed_display}")
    else:
        print_success(f"Files deleted: {deleted_count}, Space freed: {freed_display}")


def _build_task_template(task_id: str, title: str, template: str = "standard") -> dict:
    """Build a task template dict based on the chosen complexity level.

    Args:
        task_id: Unique task identifier.
        title: Human-readable title.
        template: One of "simple", "standard", "complex".

    Returns:
        A dict representing the task template.
    """
    if template == "simple":
        return {
            "task_id": task_id,
            "title": title,
            "scope": f"Implementation scope for {title}",
            "risk_level": "low",
            "priority": "medium",
            "acceptance_criteria": [
                {
                    "id": "AC-S00-1",
                    "description": "PLACEHOLDER: Define acceptance criteria",
                    "verification": "echo 'FAIL: acceptance criteria not yet defined' && exit 1",
                    "type": "automated",
                }
            ],
            "subtasks": [
                {
                    "subtask_id": f"{task_id}-S01",
                    "title": "Implementation",
                    "role": "builder",
                    "acceptance_criteria": [
                        {
                            "id": "AC-S01-1",
                            "description": "PLACEHOLDER: Define subtask criteria",
                            "verification": "echo 'FAIL: subtask criteria not yet defined' && exit 1",
                            "type": "automated",
                        }
                    ],
                }
            ],
        }

    if template == "complex":
        return {
            "task_id": task_id,
            "title": title,
            "scope": f"Implementation scope for {title}",
            "risk_level": "high",
            "priority": "high",
            "acceptance_criteria": [
                {
                    "id": "AC-S00-1",
                    "description": "PLACEHOLDER: Define overall acceptance criteria",
                    "verification": "echo 'FAIL: acceptance criteria not yet defined' && exit 1",
                    "type": "automated",
                },
                {
                    "id": "AC-S00-2",
                    "description": "PLACEHOLDER: All tests pass",
                    "verification": "echo 'FAIL: test verification not yet defined' && exit 1",
                    "type": "automated",
                },
            ],
            "subtasks": [
                {
                    "subtask_id": f"{task_id}-S01",
                    "title": "Architecture and design",
                    "role": "architect",
                    "acceptance_criteria": [
                        {
                            "id": "AC-S01-1",
                            "description": "PLACEHOLDER: Design document created",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                        {
                            "id": "AC-S01-2",
                            "description": "PLACEHOLDER: Interfaces defined",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                    ],
                },
                {
                    "subtask_id": f"{task_id}-S02",
                    "title": "Core implementation",
                    "role": "builder",
                    "acceptance_criteria": [
                        {
                            "id": "AC-S02-1",
                            "description": "PLACEHOLDER: Core logic implemented",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                        {
                            "id": "AC-S02-2",
                            "description": "PLACEHOLDER: Unit tests pass",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                    ],
                },
                {
                    "subtask_id": f"{task_id}-S03",
                    "title": "Integration and testing",
                    "role": "builder",
                    "acceptance_criteria": [
                        {
                            "id": "AC-S03-1",
                            "description": "PLACEHOLDER: Integration tests pass",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                        {
                            "id": "AC-S03-2",
                            "description": "PLACEHOLDER: Documentation updated",
                            "verification": "echo 'FAIL: criteria not yet defined' && exit 1",
                            "type": "automated",
                        },
                    ],
                },
            ],
        }

    # "standard" (default) -- matches the original template
    return {
        "task_id": task_id,
        "title": title,
        "scope": f"Implementation scope for {title}",
        "risk_level": "medium",
        "priority": "medium",
        "acceptance_criteria": [
            {
                "id": "AC-S00-1",
                "description": "PLACEHOLDER: Define overall acceptance criteria",
                "verification": "echo 'FAIL: acceptance criteria not yet defined' && exit 1",
                "type": "automated",
            }
        ],
        "subtasks": [
            {
                "subtask_id": f"{task_id}-S01",
                "title": "First subtask",
                "role": "builder",
                "acceptance_criteria": [
                    {
                        "id": "AC-S01-1",
                        "description": "PLACEHOLDER: Define subtask criteria",
                        "verification": "echo 'FAIL: subtask criteria not yet defined' && exit 1",
                        "type": "automated",
                    }
                ],
            }
        ],
    }


@click.command()
@click.option("--task-id", prompt="Task ID", help="Unique task identifier")
@click.option("--title", prompt="Task title", help="Human-readable title")
@click.option("--template", "-t", type=click.Choice(["simple", "standard", "complex"]), default="standard", help="Task template complexity")
@click.option("--output", "-o", default="", help="Output file path (default: agent/tasks/{task_id}.task.json)")
@click.pass_context
def init(ctx, task_id, title, template, output):
    """Create a new task template (interactive)."""
    from cc_collab.output import console, print_success, print_error

    logger.debug("Init task template: task_id=%s, title=%s, template=%s", task_id, title, template)

    task_data = _build_task_template(task_id, title, template)

    if not output:
        output = f"agent/tasks/{task_id}.task.json"
        logger.debug("Output path defaulted to: %s", output)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.debug("Task template written to %s", out_path)

    print_success(f"Task template created: {out_path}")
    console.print_json(json.dumps(task_data, indent=2, ensure_ascii=False))
