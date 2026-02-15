"""Utility commands: health, cleanup, init."""
import click
import json
import sys
import time
from pathlib import Path


@click.command()
@click.option("--out", default="", help="Output path for health check results")
@click.pass_context
def health(ctx, out):
    """Check CLI tool health (Claude Code, Codex CLI)."""
    from cc_collab.bridge import run_health_check
    from cc_collab.output import print_stage_result

    rc = run_health_check(out=out)
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

    for f in sorted(results.glob("*.json")):
        if not f.is_file():
            continue
        if f.stat().st_mtime >= cutoff:
            continue

        file_size = f.stat().st_size
        if dry_run:
            console.print(f"[dim][dry-run][/dim] Would delete: {f} ({file_size} bytes)")
        else:
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

    console.print()
    console.print("[bold]=== Summary ===[/bold]")
    if dry_run:
        console.print(f"Files that would be deleted: {deleted_count}")
        console.print(f"Space that would be freed:   {freed_display}")
    else:
        print_success(f"Files deleted: {deleted_count}, Space freed: {freed_display}")


@click.command()
@click.option("--task-id", prompt="Task ID", help="Unique task identifier")
@click.option("--title", prompt="Task title", help="Human-readable title")
@click.option("--output", "-o", default="", help="Output file path (default: agent/tasks/{task_id}.task.json)")
@click.pass_context
def init(ctx, task_id, title, output):
    """Create a new task template (interactive)."""
    from cc_collab.output import console, print_success, print_error

    template = {
        "task_id": task_id,
        "title": title,
        "scope": f"Implementation scope for {title}",
        "risk_level": "medium",
        "priority": "medium",
        "acceptance_criteria": [
            {
                "id": f"AC-S00-1",
                "description": "TODO: Define acceptance criteria",
                "verification": "echo TODO",
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
                        "description": "TODO: Define subtask criteria",
                        "verification": "echo TODO",
                        "type": "automated",
                    }
                ],
            }
        ],
    }

    if not output:
        output = f"agent/tasks/{task_id}.task.json"

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print_success(f"Task template created: {out_path}")
    console.print_json(json.dumps(template, indent=2, ensure_ascii=False))
