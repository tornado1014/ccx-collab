"""Pipeline stage commands: validate, plan, split, implement, merge, verify, review, retrospect."""

import sys

import click

from cc_collab.bridge import (
    run_implement,
    run_merge,
    run_plan,
    run_retrospect,
    run_review,
    run_split,
    run_validate,
    run_verify,
)
from cc_collab.config import get_platform
from cc_collab.output import print_error, print_stage_result


@click.command()
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON file")
@click.option("--work-id", default="", help="Work ID")
@click.option("--out", default="", help="Output path")
@click.pass_context
def validate(ctx, task, work_id, out):
    """Validate a task JSON file against schema."""
    rc = run_validate(task=task, work_id=work_id, out=out)
    print_stage_result("validate", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON file")
@click.option("--work-id", default="", help="Work ID")
@click.option("--out", required=True, help="Output path")
@click.pass_context
def plan(ctx, task, work_id, out):
    """Run planning phase (Claude)."""
    rc = run_plan(task=task, work_id=work_id, out=out)
    print_stage_result("plan", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON file")
@click.option("--plan", "plan_path", default="", help="Path to plan result JSON")
@click.option("--out", required=True, help="Output path")
@click.option("--matrix-output", default="", help="Dispatch matrix output path")
@click.pass_context
def split(ctx, task, plan_path, out, matrix_output):
    """Split task into execution subtasks."""
    rc = run_split(task=task, plan=plan_path, out=out, matrix_output=matrix_output)
    print_stage_result("split", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON file")
@click.option("--dispatch", default="", help="Path to dispatch JSON")
@click.option("--subtask-id", required=True, help="Subtask ID to execute")
@click.option("--work-id", default="", help="Work ID")
@click.option("--out", required=True, help="Output path")
@click.pass_context
def implement(ctx, task, dispatch, subtask_id, work_id, out):
    """Execute a single subtask implementation."""
    rc = run_implement(
        task=task, dispatch=dispatch, subtask_id=subtask_id,
        work_id=work_id, out=out,
    )
    print_stage_result("implement", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--work-id", required=True, help="Work ID")
@click.option("--kind", default="implement", help="Merge kind")
@click.option("--input", "input_glob", required=True, help="Input file glob pattern")
@click.option("--out", required=True, help="Output path")
@click.option("--dispatch", default="", help="Path to dispatch JSON")
@click.pass_context
def merge(ctx, work_id, kind, input_glob, out, dispatch):
    """Merge multiple implementation results."""
    rc = run_merge(
        work_id=work_id, kind=kind, input_glob=input_glob,
        out=out, dispatch=dispatch,
    )
    print_stage_result("merge", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--work-id", required=True, help="Work ID")
@click.option("--platform", default="", help="Platform (auto-detected if empty)")
@click.option("--out", required=True, help="Output path")
@click.option("--commands", default="", help="Verify commands (JSON array or semicolon-separated)")
@click.pass_context
def verify(ctx, work_id, platform, out, commands):
    """Run verification commands."""
    if not platform:
        platform = get_platform()
    rc = run_verify(work_id=work_id, platform=platform, out=out, commands=commands)
    print_stage_result("verify", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--work-id", required=True, help="Work ID")
@click.option("--plan", "plan_path", required=True, help="Path to plan result JSON")
@click.option("--implement", "implement_path", required=True, help="Path to implement result JSON")
@click.option("--verify", "verify_paths", multiple=True, help="Path(s) to verify result JSON")
@click.option("--out", required=True, help="Output path")
@click.pass_context
def review(ctx, work_id, plan_path, implement_path, verify_paths, out):
    """Run review gate."""
    rc = run_review(
        work_id=work_id, plan=plan_path, implement=implement_path,
        verify=list(verify_paths), out=out,
    )
    print_stage_result("review", rc, out)
    if rc != 0:
        sys.exit(rc)


@click.command()
@click.option("--work-id", required=True, help="Work ID")
@click.option("--review", "review_path", required=True, help="Path to review result JSON")
@click.option("--out", required=True, help="Output path")
@click.pass_context
def retrospect(ctx, work_id, review_path, out):
    """Generate retrospective and next action plan."""
    rc = run_retrospect(work_id=work_id, review=review_path, out=out)
    print_stage_result("retrospect", rc, out)
    if rc != 0:
        sys.exit(rc)
