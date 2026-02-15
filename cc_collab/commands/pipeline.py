"""Pipeline commands: run (full pipeline) and status."""
import click
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


@click.command("run")
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON")
@click.option("--work-id", default="", help="Work ID (auto-generated if empty)")
@click.option("--results-dir", default="agent/results", help="Results directory")
@click.option("--mode", type=click.Choice(["full", "implement-only"]), default="full", help="Pipeline mode")
@click.pass_context
def run(ctx, task, work_id, results_dir, mode):
    """Run the full 7-stage pipeline."""
    from cc_collab.bridge import (
        run_validate, run_plan, run_split,
        run_implement, run_merge, run_verify,
        run_review, run_retrospect, setup_simulate_mode,
    )
    from cc_collab.config import get_platform
    from cc_collab.output import console, print_error, print_success

    # Simulate mode
    if ctx.obj.get("simulate", False):
        setup_simulate_mode(True)

    # Auto-generate work_id from task file hash
    task_path = Path(task)
    if not work_id:
        work_id = hashlib.sha256(task_path.read_bytes()).hexdigest()[:12]

    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)

    platform = get_platform()

    # Path templates
    validation_path = f"{results_dir}/validation_{work_id}.json"
    plan_path = f"{results_dir}/plan_{work_id}.json"
    dispatch_path = f"{results_dir}/dispatch_{work_id}.json"
    dispatch_matrix_path = f"{results_dir}/dispatch_{work_id}.matrix.json"
    implement_path = f"{results_dir}/implement_{work_id}.json"
    verify_path = f"{results_dir}/verify_{work_id}_{platform}.json"
    review_path = f"{results_dir}/review_{work_id}.json"
    retrospect_path = f"{results_dir}/retrospect_{work_id}.json"

    console.print("[bold]=== Pipeline Runner ===[/bold]")
    console.print(f"Task:    {task}")
    console.print(f"Work ID: {work_id}")
    console.print(f"Mode:    {mode}")
    console.print(f"Results: {results_dir}")
    console.print()

    stages = [
        ("1", "Validating task"),
        ("2", "Planning (Claude)"),
        ("3", "Splitting task"),
        ("4", "Implementing subtasks"),
        ("5", "Merging results"),
        ("6", "Verifying"),
        ("7", "Reviewing & retrospective"),
    ]

    def _run_stage(num, label, fn):
        total = "7" if mode == "full" else "5"
        console.print(f"[bold cyan][{num}/{total}][/bold cyan] {label}...")
        rc = fn()
        if rc != 0:
            print_error(f"Stage {label} failed (exit code {rc})")
            sys.exit(rc)

    # Stage 1: Validate
    _run_stage("1", stages[0][1], lambda: run_validate(
        task=task, work_id=work_id, out=validation_path,
    ))

    # Stage 2: Plan
    _run_stage("2", stages[1][1], lambda: run_plan(
        task=task, work_id=work_id, out=plan_path,
    ))

    # Stage 3: Split
    _run_stage("3", stages[2][1], lambda: run_split(
        task=task, plan=plan_path, out=dispatch_path,
        matrix_output=dispatch_matrix_path,
    ))

    # Stage 4: Implement (parallel subtasks)
    console.print(f"[bold cyan][4/{'7' if mode == 'full' else '5'}][/bold cyan] {stages[3][1]}...")
    dispatch_data = json.loads(Path(dispatch_path).read_text(encoding="utf-8"))
    subtasks = dispatch_data.get("subtasks", [])

    impl_failures = 0
    if subtasks:
        def _run_subtask(st):
            subtask_id = st["subtask_id"]
            role = st.get("role", st.get("owner", "builder"))
            if role == "claude":
                role = "architect"
            elif role == "codex":
                role = "builder"
            out = f"{results_dir}/implement_{work_id}_{subtask_id}.json"
            console.print(f"  -> {subtask_id} (role={role})")
            return run_implement(
                task=task, dispatch=dispatch_path,
                subtask_id=subtask_id, work_id=work_id, out=out,
            )

        with ThreadPoolExecutor(max_workers=min(4, len(subtasks))) as executor:
            futures = {executor.submit(_run_subtask, st): st for st in subtasks}
            for future in as_completed(futures):
                rc = future.result()
                if rc != 0:
                    impl_failures += 1

    if impl_failures > 0:
        print_error(f"{impl_failures} implementation job(s) failed.")
        sys.exit(1)

    # Stage 5: Merge
    _run_stage("5", stages[4][1], lambda: run_merge(
        work_id=work_id, kind="implement",
        results_dir=results_dir, dispatch=dispatch_path,
        out=implement_path,
    ))

    if mode == "implement-only":
        console.print()
        print_success(f"implement-only mode complete. Output: {implement_path}")
        return

    # Stage 6: Verify
    _run_stage("6", stages[5][1], lambda: run_verify(
        work_id=work_id, platform=platform, out=verify_path,
    ))

    # Stage 7: Review + Retrospect
    console.print(f"[bold cyan][7/7][/bold cyan] {stages[6][1]}...")
    rc = run_review(
        work_id=work_id, plan=plan_path,
        implement=implement_path, verify=verify_path, out=review_path,
    )
    if rc != 0:
        print_error(f"Review failed (exit code {rc})")
        sys.exit(rc)

    rc = run_retrospect(
        work_id=work_id, review=review_path, out=retrospect_path,
    )
    if rc != 0:
        print_error(f"Retrospect failed (exit code {rc})")
        sys.exit(rc)

    console.print()
    console.print("[bold]=== Pipeline Complete ===[/bold]")
    print_success(f"Review:        {review_path}")
    print_success(f"Retrospective: {retrospect_path}")


@click.command()
@click.option("--work-id", required=True, help="Work ID to check")
@click.option("--results-dir", default="agent/results", help="Results directory")
@click.pass_context
def status(ctx, work_id, results_dir):
    """Show pipeline progress for a work ID."""
    from cc_collab.config import get_platform
    from cc_collab.output import console

    platform = get_platform()
    results = Path(results_dir)

    stage_files = [
        ("validate", f"validation_{work_id}.json"),
        ("plan", f"plan_{work_id}.json"),
        ("split", f"dispatch_{work_id}.json"),
        ("implement", f"implement_{work_id}.json"),
        ("verify", f"verify_{work_id}_{platform}.json"),
        ("review", f"review_{work_id}.json"),
        ("retrospect", f"retrospect_{work_id}.json"),
    ]

    from rich.table import Table

    table = Table(title=f"Pipeline Status: {work_id}")
    table.add_column("Stage", style="cyan")
    table.add_column("File", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Result")

    for stage_name, filename in stage_files:
        filepath = results / filename
        if filepath.exists():
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                result_status = data.get("status", "unknown")
                status_style = "green" if result_status == "passed" else "yellow"
                table.add_row(stage_name, filename, "[green]done[/green]", f"[{status_style}]{result_status}[/{status_style}]")
            except (json.JSONDecodeError, OSError):
                table.add_row(stage_name, filename, "[green]done[/green]", "[red]parse error[/red]")
        else:
            table.add_row(stage_name, filename, "[dim]missing[/dim]", "")

    console.print(table)
