"""Pipeline stage commands: validate, plan, split, implement, merge, verify, review, retrospect."""

import logging
import sys

import click

logger = logging.getLogger(__name__)

from ccx_collab.bridge import (
    run_implement,
    run_merge,
    run_plan,
    run_retrospect,
    run_review,
    run_split,
    run_validate,
    run_verify,
)
from ccx_collab.config import get_platform
from ccx_collab.output import print_error, print_stage_result


@click.command()
@click.option("--task", required=True, type=click.Path(exists=True), help="Path to task JSON file")
@click.option("--work-id", default="", help="Work ID")
@click.option("--out", default="", help="Output path")
@click.pass_context
def validate(ctx, task, work_id, out):
    """Validate a task JSON file against schema."""
    logger.debug("Stage 'validate' starting: task=%s, work_id=%s, out=%s", task, work_id, out)
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
    logger.debug("Stage 'plan' starting: task=%s, work_id=%s, out=%s", task, work_id, out)
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
    logger.debug("Stage 'split' starting: task=%s, plan=%s, out=%s, matrix_output=%s",
                 task, plan_path, out, matrix_output)
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
    logger.debug("Stage 'implement' starting: task=%s, subtask_id=%s, work_id=%s, out=%s",
                 task, subtask_id, work_id, out)
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
@click.option(
    "--input", "input_glob", default="",
    help="Explicit glob pattern for input files (e.g. 'results/impl_*.json'). "
    "Takes precedence over --results-dir if both are provided.",
)
@click.option(
    "--results-dir", default="",
    help="Results directory from which to auto-construct the glob pattern "
    "as '<results-dir>/<kind>_<work-id>_*.json'. "
    "Used when --input is not provided.",
)
@click.option("--out", required=True, help="Output path")
@click.option("--dispatch", default="", help="Path to dispatch JSON")
@click.pass_context
def merge(ctx, work_id, kind, input_glob, results_dir, out, dispatch):
    """Merge multiple implementation results.

    Accepts input files via two mutually-compatible options:

    \b
      --input        Explicit glob pattern (e.g. "results/impl_*.json").
      --results-dir  Auto-construct glob: <results-dir>/<kind>_<work-id>_*.json.

    If both are provided, --input takes precedence.
    At least one of --input or --results-dir must be supplied.
    """
    logger.debug("Stage 'merge' starting: work_id=%s, kind=%s, input=%s, results_dir=%s, out=%s",
                 work_id, kind, input_glob, results_dir, out)
    rc = run_merge(
        work_id=work_id, kind=kind, input_glob=input_glob,
        results_dir=results_dir, out=out, dispatch=dispatch,
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
        logger.debug("Platform auto-detected as '%s'", platform)
    logger.debug("Stage 'verify' starting: work_id=%s, platform=%s, out=%s",
                 work_id, platform, out)
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
    logger.debug("Stage 'review' starting: work_id=%s, plan=%s, implement=%s, verify=%s, out=%s",
                 work_id, plan_path, implement_path, list(verify_paths), out)
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
    logger.debug("Stage 'retrospect' starting: work_id=%s, review=%s, out=%s",
                 work_id, review_path, out)
    rc = run_retrospect(work_id=work_id, review=review_path, out=out)
    print_stage_result("retrospect", rc, out)
    if rc != 0:
        sys.exit(rc)
