"""Bridge to orchestrate.py — wraps action functions for direct Python invocation."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def _ensure_orchestrate_importable() -> None:
    """Add agent/scripts to sys.path so orchestrate can be imported."""
    scripts_dir = str(Path(__file__).resolve().parents[1] / "agent" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
        logger.debug("Added orchestrate scripts dir to sys.path: %s", scripts_dir)


_ensure_orchestrate_importable()
import orchestrate  # noqa: E402


def setup_simulate_mode(simulate: bool) -> None:
    """Set SIMULATE_AGENTS env var."""
    if simulate:
        os.environ["SIMULATE_AGENTS"] = "1"
        logger.debug("SIMULATE_AGENTS env var set to 1")
    elif "SIMULATE_AGENTS" in os.environ:
        del os.environ["SIMULATE_AGENTS"]
        logger.debug("SIMULATE_AGENTS env var removed")


def run_validate(task: str, work_id: str = "", out: str = "") -> int:
    logger.debug("run_validate called: task=%s, work_id=%s, out=%s", task, work_id, out)
    args = argparse.Namespace(task=task, work_id=work_id, out=out)
    rc = orchestrate.action_validate_task(args)
    logger.info("run_validate completed with exit code %d", rc)
    return rc


def run_plan(task: str, work_id: str = "", out: str = "") -> int:
    logger.debug("run_plan called: task=%s, work_id=%s, out=%s", task, work_id, out)
    args = argparse.Namespace(task=task, work_id=work_id, out=out)
    rc = orchestrate.action_run_plan(args)
    logger.info("run_plan completed with exit code %d", rc)
    return rc


def run_split(
    task: str, plan: str = "", out: str = "", matrix_output: str = "",
) -> int:
    logger.debug("run_split called: task=%s, plan=%s, out=%s, matrix_output=%s",
                 task, plan, out, matrix_output)
    args = argparse.Namespace(task=task, plan=plan, out=out, matrix_output=matrix_output)
    rc = orchestrate.action_split_task(args)
    logger.info("run_split completed with exit code %d", rc)
    return rc


def run_implement(
    task: str,
    dispatch: str = "",
    subtask_id: str = "",
    work_id: str = "",
    out: str = "",
) -> int:
    logger.debug("run_implement called: task=%s, subtask_id=%s, work_id=%s, out=%s",
                 task, subtask_id, work_id, out)
    args = argparse.Namespace(
        task=task, dispatch=dispatch, subtask_id=subtask_id,
        work_id=work_id, out=out,
    )
    rc = orchestrate.action_run_implement(args)
    logger.info("run_implement completed with exit code %d (subtask=%s)", rc, subtask_id)
    return rc


def run_merge(
    work_id: str,
    kind: str = "implement",
    input_glob: str = "",
    out: str = "",
    dispatch: str = "",
    results_dir: str = "",
) -> int:
    """Merge implementation results.

    Either *input_glob* (explicit glob pattern) or *results_dir* (directory
    from which the glob is auto-constructed) must be provided.  If both are
    given, *input_glob* takes precedence.

    Returns 1 immediately when neither parameter is supplied.
    """
    logger.debug("run_merge called: work_id=%s, kind=%s, input_glob=%s, "
                 "results_dir=%s, out=%s", work_id, kind, input_glob, results_dir, out)
    # input_glob takes precedence; fall back to results_dir construction
    if not input_glob and results_dir:
        input_glob = f"{results_dir}/{kind}_{work_id}_*.json"
        logger.debug("Constructed input glob from results_dir: %s", input_glob)

    if not input_glob:
        logger.error(
            "run_merge requires either input_glob or results_dir. "
            "Hint: pass --input <glob> or --results-dir <dir>."
        )
        return 1

    args = argparse.Namespace(work_id=work_id, kind=kind, out=out, dispatch=dispatch)
    # 'input' is a Python builtin, use setattr
    setattr(args, "input", input_glob)
    rc = orchestrate.action_merge_results(args)
    logger.info("run_merge completed with exit code %d", rc)
    return rc


def run_verify(
    work_id: str, platform: str = "", out: str = "", commands: str = "",
) -> int:
    logger.debug("run_verify called: work_id=%s, platform=%s, out=%s", work_id, platform, out)
    args = argparse.Namespace(
        work_id=work_id, platform=platform, out=out, commands=commands,
    )
    rc = orchestrate.action_run_verify(args)
    logger.info("run_verify completed with exit code %d", rc)
    return rc


def run_review(
    work_id: str,
    plan: str = "",
    implement: str = "",
    verify: Optional[str | List[str]] = None,
    out: str = "",
) -> int:
    logger.debug("run_review called: work_id=%s, out=%s", work_id, out)
    # Normalize verify to a list
    if verify is None:
        verify_list: List[str] = []
    elif isinstance(verify, str):
        verify_list = [verify] if verify else []
    else:
        verify_list = list(verify)
    logger.debug("run_review verify paths: %s", verify_list)
    args = argparse.Namespace(
        work_id=work_id, plan=plan, implement=implement,
        verify=verify_list, out=out,
    )
    rc = orchestrate.action_review(args)
    logger.info("run_review completed with exit code %d", rc)
    return rc


def run_retrospect(work_id: str, review: str = "", out: str = "") -> int:
    logger.debug("run_retrospect called: work_id=%s, review=%s, out=%s", work_id, review, out)
    args = argparse.Namespace(work_id=work_id, review=review, out=out)
    rc = orchestrate.action_retrospect(args)
    logger.info("run_retrospect completed with exit code %d", rc)
    return rc


def run_health_check(out: str = "") -> int:
    logger.debug("run_health_check called: out=%s", out)
    args = argparse.Namespace(out=out)
    rc = orchestrate.action_health_check(args)
    logger.info("run_health_check completed with exit code %d", rc)
    return rc
