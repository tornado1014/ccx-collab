"""Bridge to orchestrate.py — wraps action functions for direct Python invocation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional


def _ensure_orchestrate_importable() -> None:
    """Add agent/scripts to sys.path so orchestrate can be imported."""
    scripts_dir = str(Path(__file__).resolve().parents[1] / "agent" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)


_ensure_orchestrate_importable()
import orchestrate  # noqa: E402


def setup_simulate_mode(simulate: bool) -> None:
    """Set SIMULATE_AGENTS env var."""
    if simulate:
        os.environ["SIMULATE_AGENTS"] = "1"
    elif "SIMULATE_AGENTS" in os.environ:
        del os.environ["SIMULATE_AGENTS"]


def run_validate(task: str, work_id: str = "", out: str = "") -> int:
    args = argparse.Namespace(task=task, work_id=work_id, out=out)
    return orchestrate.action_validate_task(args)


def run_plan(task: str, work_id: str = "", out: str = "") -> int:
    args = argparse.Namespace(task=task, work_id=work_id, out=out)
    return orchestrate.action_run_plan(args)


def run_split(
    task: str, plan: str = "", out: str = "", matrix_output: str = "",
) -> int:
    args = argparse.Namespace(task=task, plan=plan, out=out, matrix_output=matrix_output)
    return orchestrate.action_split_task(args)


def run_implement(
    task: str,
    dispatch: str = "",
    subtask_id: str = "",
    work_id: str = "",
    out: str = "",
) -> int:
    args = argparse.Namespace(
        task=task, dispatch=dispatch, subtask_id=subtask_id,
        work_id=work_id, out=out,
    )
    return orchestrate.action_run_implement(args)


def run_merge(
    work_id: str,
    kind: str = "implement",
    input_glob: str = "",
    out: str = "",
    dispatch: str = "",
    results_dir: str = "",
) -> int:
    # Construct input glob from results_dir if input_glob not provided
    if not input_glob and results_dir:
        input_glob = f"{results_dir}/{kind}_{work_id}_*.json"
    args = argparse.Namespace(work_id=work_id, kind=kind, out=out, dispatch=dispatch)
    # 'input' is a Python builtin, use setattr
    setattr(args, "input", input_glob)
    return orchestrate.action_merge_results(args)


def run_verify(
    work_id: str, platform: str = "", out: str = "", commands: str = "",
) -> int:
    args = argparse.Namespace(
        work_id=work_id, platform=platform, out=out, commands=commands,
    )
    return orchestrate.action_run_verify(args)


def run_review(
    work_id: str,
    plan: str = "",
    implement: str = "",
    verify: Optional[str | List[str]] = None,
    out: str = "",
) -> int:
    # Normalize verify to a list
    if verify is None:
        verify_list: List[str] = []
    elif isinstance(verify, str):
        verify_list = [verify] if verify else []
    else:
        verify_list = list(verify)
    args = argparse.Namespace(
        work_id=work_id, plan=plan, implement=implement,
        verify=verify_list, out=out,
    )
    return orchestrate.action_review(args)


def run_retrospect(work_id: str, review: str = "", out: str = "") -> int:
    args = argparse.Namespace(work_id=work_id, review=review, out=out)
    return orchestrate.action_retrospect(args)


def run_health_check(out: str = "") -> int:
    args = argparse.Namespace(out=out)
    return orchestrate.action_health_check(args)
