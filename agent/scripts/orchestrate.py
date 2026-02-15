#!/usr/bin/env python3
"""Orchestrator primitives for Claude + Codex cross-platform workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pathlib
import shlex
import subprocess
import sys
import time
import datetime
import platform as _platform
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("orchestrate")

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

ROOT = pathlib.Path(__file__).resolve().parents[1]
TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(TIMESTAMP_FMT)


def ensure_parent(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def acquire_lock(path: pathlib.Path):
    """Acquire a file lock (non-blocking). Returns file descriptor or raises."""
    lock_path = path.with_suffix(".lock")
    ensure_parent(lock_path)
    fd = open(lock_path, "w")
    try:
        if _platform.system() == "Windows":
            import msvcrt
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        fd.close()
        raise
    return fd


def release_lock(fd) -> None:
    """Release a file lock."""
    try:
        fd.close()
    except Exception:
        pass


def load_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_subtask_role(subtask: Dict[str, Any]) -> str:
    """Determine subtask role: architect (Claude) or builder (Codex)."""
    if "role" in subtask:
        role = str(subtask["role"]).strip().lower()
        if role in {"architect", "builder"}:
            return role
    if subtask.get("owner") == "claude":
        return "architect"
    if subtask.get("owner") == "codex":
        return "builder"
    return "builder"


def normalize_platform(platform_value: Any) -> List[str]:
    if platform_value is None:
        return ["both"]
    if isinstance(platform_value, str):
        return [p.strip().lower() for p in platform_value.split(",") if p.strip()]
    if isinstance(platform_value, (list, tuple)):
        return [str(p).strip().lower() for p in platform_value if str(p).strip()]
    return ["both"]


def normalize_task(task: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    normalized = dict(task)

    if "task_id" not in normalized or not str(normalized.get("task_id", "")).strip():
        errors.append("missing task_id")
        normalized["task_id"] = normalized.get("task_id") or "task-unknown"

    for key in ["title", "scope", "risk_level", "priority"]:
        if not str(normalized.get(key, "")).strip():
            errors.append(f"missing {key}")
            normalized[key] = str(normalized.get(key, "")).strip() or "unknown"

    if not isinstance(normalized.get("acceptance_criteria"), list) or not normalized["acceptance_criteria"]:
        errors.append("acceptance_criteria must be a non-empty array")
        if not isinstance(normalized.get("acceptance_criteria"), list):
            normalized["acceptance_criteria"] = []

    platforms = normalize_platform(normalized.get("platform"))
    normalized["platform"] = [p for p in platforms if p in {"mac", "windows", "both"}] or ["both"]

    subtasks = normalized.get("subtasks", [])
    if isinstance(subtasks, dict):
        errors.append("subtasks should be an array")
        subtasks = [subtasks]

    if not isinstance(subtasks, list):
        subtasks = []

    normalized_subtasks: List[Dict[str, Any]] = []
    for index, subtask in enumerate(subtasks, start=1):
        if isinstance(subtask, str):
            normalized_subtasks.append({
                "subtask_id": f"{normalized.get('task_id', 'task')}-S{index:02d}",
                "title": subtask,
                "platform": normalized.get("platform", ["both"]),
                "scope": normalized.get("scope", ""),
                "acceptance_criteria": normalized.get("acceptance_criteria", []),
            })
            continue

        if not isinstance(subtask, dict):
            errors.append(f"subtask index={index} must be object or string")
            continue

        normalized_subtask: Dict[str, Any] = dict(subtask)
        normalized_subtask["subtask_id"] = normalized_subtask.get("subtask_id") or f"{normalized.get('task_id', 'task')}-S{index:02d}"
        normalized_subtask["title"] = str(normalized_subtask.get("title", "") or normalized.get("title", "")).strip() or "untitled"
        normalized_subtask["platform"] = normalize_platform(subtask.get("platform", normalized.get("platform", ["both"])))
        normalized_subtask["scope"] = str(normalized_subtask.get("scope", normalized.get("scope", ""))).strip() or "implementation"
        normalized_subtask["acceptance_criteria"] = normalized_subtask.get(
            "acceptance_criteria",
            normalized.get("acceptance_criteria", []),
        )
        if not isinstance(normalized_subtask["acceptance_criteria"], list):
            normalized_subtask["acceptance_criteria"] = list(normalized.get("acceptance_criteria", []))

        normalized_subtasks.append(normalized_subtask)

    if not normalized_subtasks:
        normalized_subtasks.append(
            {
                "subtask_id": f"{normalized.get('task_id', 'task')}-S01",
                "title": normalized.get("title", "untitled"),
                "platform": normalized.get("platform", ["both"]),
                "scope": normalized.get("scope", "implementation"),
                "acceptance_criteria": normalized.get("acceptance_criteria", []),
            }
        )

    normalized["subtasks"] = normalized_subtasks
    return normalized, errors


def command_output_trace(cmd: str) -> str:
    return cmd[:180] + "..." if len(cmd) > 180 else cmd


def run_agent_command(agent: str, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    max_retries = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    retry_wait = int(os.getenv("AGENT_RETRY_SLEEP", "20"))
    cli_timeout = int(os.getenv("CLI_TIMEOUT_SECONDS", "300"))
    allow_simulation = os.getenv("SIMULATE_AGENTS", "0").strip() in {"1", "true", "TRUE", "True"}

    if not command:
        if not allow_simulation:
            raise RuntimeError(
                f"{agent} CLI command not configured. Set { 'CLAUDE_CODE_CMD' if agent == 'claude' else 'CODEX_CLI_CMD' } or enable SIMULATE_AGENTS=1."
            )
        return {
            "status": "simulated",
            "command": "",
            "return_code": 0,
            "stdout": f"[{agent}] simulation mode",
            "stderr": "",
            "retries": 0,
            "elapsed_ms": 0,
        }

    payload_text = json.dumps(payload, ensure_ascii=False)
    attempt = 0
    last = None

    for attempt in range(1, max_retries + 1):
        start = time.perf_counter()
        try:
            if _platform.system() == "Windows":
                proc = subprocess.run(
                    command,
                    shell=True,
                    input=payload_text,
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                    timeout=cli_timeout,
                )
            else:
                proc = subprocess.run(
                    shlex.split(command),
                    shell=False,
                    input=payload_text,
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                    timeout=cli_timeout,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            result = {
                "status": "failed",
                "command": command,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {cli_timeout}s",
                "attempt": attempt,
                "elapsed_ms": elapsed_ms,
                "payload_checksum": sha256_bytes(payload_text.encode("utf-8")),
            }
            last = result
            if attempt < max_retries:
                time.sleep(max(0, retry_wait))
            continue
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        result = {
            "status": "passed" if proc.returncode == 0 else "failed",
            "command": command,
            "return_code": proc.returncode,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "attempt": attempt,
            "elapsed_ms": elapsed_ms,
            "payload_checksum": sha256_bytes(payload_text.encode("utf-8")),
        }
        if proc.returncode == 0:
            return result

        last = result
        if attempt < max_retries:
            time.sleep(max(0, retry_wait))

    if last is None:
        last = {
            "status": "failed",
            "command": command,
            "return_code": 1,
            "stdout": "",
            "stderr": "no attempt made",
            "attempt": attempt,
            "elapsed_ms": 0,
            "payload_checksum": sha256_bytes(payload_text.encode("utf-8")),
        }
    return last


def parse_cli_envelope(stdout_text: str) -> Dict[str, Any]:
    """Parse CLI envelope output. Returns {"envelope": {...}, "result": {...}}."""
    if not stdout_text:
        return {"envelope": {"status": "failed"}, "result": {}}
    try:
        envelope = json.loads(stdout_text)
        if isinstance(envelope, dict) and "status" in envelope and "stdout" in envelope:
            inner_stdout = envelope.get("stdout", "")
            try:
                inner = json.loads(inner_stdout)
                return {"envelope": envelope, "result": inner.get("result", inner) if isinstance(inner, dict) else {}}
            except (json.JSONDecodeError, TypeError):
                return {"envelope": envelope, "result": envelope.get("result", {}) if isinstance(envelope, dict) else {}}
        if isinstance(envelope, dict):
            return {"envelope": envelope, "result": envelope.get("result", envelope)}
        return {"envelope": {"status": "failed"}, "result": {}}
    except json.JSONDecodeError:
        return {"envelope": {"status": "failed"}, "result": {}}


def parse_verify_commands(raw: str) -> List[str]:
    if not raw:
        return []

    raw = raw.strip()
    if not raw:
        return []

    try:
        loaded = json.loads(raw)
        if isinstance(loaded, list):
            return [str(cmd).strip() for cmd in loaded if str(cmd).strip()]
    except Exception:
        pass

    commands: List[str] = []
    for line in raw.replace(";", "\n").splitlines():
        candidate = line.strip()
        if candidate:
            commands.append(candidate)
    return commands


def write_with_meta(agent: str, work_id: str, payload: Dict[str, Any], path: pathlib.Path) -> Dict[str, Any]:
    report = {
        "agent": agent,
        "work_id": work_id,
        "generated_at": now_iso(),
        "checksum": sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")),
    }
    report.update(payload)
    write_json(path, report)
    return report


def action_validate_task(args: argparse.Namespace) -> int:
    task_path = pathlib.Path(args.task)
    task = load_json(task_path)
    normalized, errors = normalize_task(task)

    schema_path = ROOT / "schemas" / "task.schema.json"
    if schema_path.exists() and jsonschema is not None:
        schema = load_json(schema_path)
        try:
            jsonschema.validate(normalized, schema)
        except jsonschema.ValidationError as ve:
            errors.append(f"Schema violation: {ve.message} at {list(ve.absolute_path)}")
        except jsonschema.SchemaError as se:
            errors.append(f"Invalid schema: {se.message}")
    elif jsonschema is None:
        errors.append("jsonschema package not installed — schema validation skipped")

    payload: Dict[str, Any] = {
        "work_id": normalized.get("task_id", "task-unknown"),
        "status": "blocked" if errors else "ready",
        "validation_errors": errors,
        "task": normalized,
    }
    if args.out:
        write_with_meta("validation", normalized.get("task_id", "task-unknown"), payload, pathlib.Path(args.out))
    else:
        write_with_meta("validation", normalized.get("task_id", "task-unknown"), payload, pathlib.Path(f"agent/results/validation_{normalized.get('task_id','task-unknown')}.json"))

    if errors:
        return 2
    return 0


def action_split_task(args: argparse.Namespace) -> int:
    task = load_json(pathlib.Path(args.task))
    task, errors = normalize_task(task)
    if errors:
        logger.warning("Task is invalid. Run validate-task first.")
        return 2

    plan_file = pathlib.Path(args.plan) if args.plan else None
    if plan_file and plan_file.exists():
        plan = load_json(plan_file)
    else:
        plan = {}

    implementation_contract = plan.get("implementation_contract", []) if isinstance(plan, dict) else []
    test_plan = plan.get("test_plan", []) if isinstance(plan, dict) else []
    plan_chunks = plan.get("chunks", []) if isinstance(plan, dict) else []

    subtasks: List[Dict[str, Any]] = []
    matrix: List[Dict[str, Any]] = []

    if plan_chunks:
        for chunk in plan_chunks:
            role = chunk.get("role", "builder")
            owner = "claude" if role == "architect" else "codex"
            subtask_id = chunk.get("chunk_id", chunk.get("subtask_id", "unknown"))

            entry_out = {
                "subtask_id": subtask_id,
                "title": chunk.get("title", "untitled"),
                "role": role,
                "owner": owner,
                "scope": chunk.get("scope", task.get("scope", "implementation")),
                "estimated_minutes": chunk.get("estimated_minutes", 60),
                "depends_on": chunk.get("depends_on", []),
                "files_affected": chunk.get("files_affected", []),
                "acceptance_criteria": chunk.get("acceptance_criteria", []),
                "notes": chunk.get("notes", []),
                "work_id": task["task_id"],
                "risk_level": task.get("risk_level", "medium"),
                "source_subtask_id": chunk.get("source_subtask_id"),
            }
            subtasks.append(entry_out)

            matrix.append({
                "subtask_id": subtask_id,
                "role": role,
                "owner": owner,
                "estimated_minutes": chunk.get("estimated_minutes", 60),
                "depends_on": chunk.get("depends_on", []),
            })
    else:
        for entry in task["subtasks"]:
            role = normalize_subtask_role(entry)
            owner = "claude" if role == "architect" else "codex"

            entry_out = {
                "subtask_id": entry["subtask_id"],
                "title": entry["title"],
                "role": role,
                "owner": owner,
                "scope": entry.get("scope", task.get("scope", "implementation")),
                "estimated_minutes": entry.get("estimated_minutes", 60),
                "depends_on": entry.get("depends_on", []),
                "files_affected": entry.get("files_affected", []),
                "acceptance_criteria": entry.get("acceptance_criteria", task.get("acceptance_criteria", [])),
                "notes": entry.get("notes", []),
                "work_id": task["task_id"],
                "risk_level": task.get("risk_level", "medium"),
            }
            subtasks.append(entry_out)

            matrix.append({
                "subtask_id": entry["subtask_id"],
                "role": role,
                "owner": owner,
                "estimated_minutes": entry.get("estimated_minutes", 60),
                "depends_on": entry.get("depends_on", []),
            })

    payload = {
        "work_id": task["task_id"],
        "status": "done",
        "plan_version": task.get("plan_version", "v1"),
        "subtasks": subtasks,
        "dispatch_from_plan": {
            "implementation_contract": implementation_contract,
            "test_plan": test_plan,
        },
    }

    out = pathlib.Path(args.out)
    write_with_meta("dispatch", task["task_id"], payload, out)

    if args.matrix_output:
        ensure_parent(pathlib.Path(args.matrix_output))
        pathlib.Path(args.matrix_output).write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


def build_report_status(values: Sequence[str]) -> str:
    if "failed" in values:
        return "failed"
    if "skipped" in values:
        return "failed"
    if "blocked" in values:
        return "blocked"
    if "simulated" in values:
        return "done"  # simulated treated as done for pipeline flow
    if "passed" in values:
        return "done"
    if "ready" in values:
        return "ready"
    return "done"


def as_payload(node: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(node, dict) and "payload" in node and isinstance(node["payload"], dict):
        return node["payload"]
    return node


def build_chunks_from_subtasks(task: Dict[str, Any], plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build 30-90 minute implementation chunks from subtasks.

    If the CLI returned structured chunks, use those. Otherwise, generate
    chunks from the task subtasks, splitting any that exceed 90 minutes.
    """
    if isinstance(plan_data.get("chunks"), list) and plan_data["chunks"]:
        return plan_data["chunks"]

    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for subtask in task.get("subtasks", []):
        est = subtask.get("estimated_minutes", 60)
        if est < 30:
            est = 30
        role = normalize_subtask_role(subtask)

        raw_criteria = subtask.get("acceptance_criteria", [])
        machine_criteria = normalize_acceptance_criteria(
            raw_criteria, subtask.get("subtask_id", "S00")
        )

        if est <= 90:
            chunk_index += 1
            chunks.append({
                "chunk_id": f"{task['task_id']}-C{chunk_index:02d}",
                "title": subtask.get("title", "untitled"),
                "estimated_minutes": est,
                "role": role,
                "depends_on": subtask.get("depends_on", []),
                "scope": subtask.get("scope", task.get("scope", "")),
                "files_affected": subtask.get("files_affected", []),
                "acceptance_criteria": machine_criteria,
                "source_subtask_id": subtask.get("subtask_id"),
            })
        else:
            num_splits = (est + 89) // 90
            per_chunk = est // num_splits
            criteria_per = max(1, len(machine_criteria) // num_splits)
            for split_i in range(num_splits):
                chunk_index += 1
                start_ac = split_i * criteria_per
                end_ac = start_ac + criteria_per if split_i < num_splits - 1 else len(machine_criteria)
                split_criteria = machine_criteria[start_ac:end_ac] or machine_criteria[:1]
                depends = subtask.get("depends_on", [])
                if split_i > 0:
                    depends = [f"{task['task_id']}-C{chunk_index - 1:02d}"]
                chunks.append({
                    "chunk_id": f"{task['task_id']}-C{chunk_index:02d}",
                    "title": f"{subtask.get('title', 'untitled')} (part {split_i + 1}/{num_splits})",
                    "estimated_minutes": min(90, max(30, per_chunk)),
                    "role": role,
                    "depends_on": depends,
                    "scope": subtask.get("scope", task.get("scope", "")),
                    "files_affected": subtask.get("files_affected", []),
                    "acceptance_criteria": split_criteria,
                    "source_subtask_id": subtask.get("subtask_id"),
                })

    return chunks


def normalize_acceptance_criteria(raw: List[Any], subtask_id: str) -> List[Dict[str, Any]]:
    """Convert mixed string/object acceptance criteria into machine-readable format."""
    result: List[Dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict) and "id" in item and "verification" in item:
            result.append({
                "id": item["id"],
                "description": item.get("description", ""),
                "verify_command": item.get("verification", item.get("verify_command", "echo 'manual check required'")),
                "verify_pattern": item.get("verify_pattern", ""),
                "category": item.get("category", item.get("type", "functional")),
            })
        elif isinstance(item, str):
            ac_id = f"AC-{subtask_id}-{index}"
            result.append({
                "id": ac_id,
                "description": item,
                "verify_command": f"echo 'TODO: implement verification for: {item}'",
                "verify_pattern": "",
                "category": "functional",
            })
    return result


def action_run_plan(args: argparse.Namespace) -> int:
    task = load_json(pathlib.Path(args.task))
    task, errors = normalize_task(task)
    if errors:
        return 2

    command = os.getenv("CLAUDE_CODE_CMD", "").strip()
    work_id = args.work_id or task["task_id"]

    payload = {
        "work_id": work_id,
        "phase": "plan",
        "task": task,
        "request": (
            "Plan stage: split to 30-90 min implementation chunks and add machine-readable acceptance criteria. "
            "Return JSON with 'chunks' array where each chunk has: chunk_id, title, estimated_minutes (30-90), "
            "role (architect|builder), depends_on (array), scope, files_affected (array), and acceptance_criteria "
            "(array of {id, description, verify_command, verify_pattern, category})."
        ),
    }

    cli = run_agent_command("claude", command, payload)
    parsed = parse_cli_envelope(cli.get("stdout", ""))
    plan_data = parsed["result"]

    cli_status = cli["status"]
    status = "done" if cli_status in ("passed", "simulated") else "blocked"

    chunks = build_chunks_from_subtasks(task, plan_data)

    top_level_criteria = normalize_acceptance_criteria(
        plan_data.get("acceptance_criteria", task.get("acceptance_criteria", [])),
        task.get("task_id", "T00"),
    )

    result = {
        "status": status,
        "implementation_contract": [
            c["description"] if isinstance(c, dict) else c
            for c in plan_data.get("acceptance_criteria", task.get("acceptance_criteria", []))
        ],
        "test_plan": plan_data.get("test_plan", parse_verify_commands(os.getenv("VERIFY_COMMANDS", ""))),
        "open_questions": [],
        "chunks": chunks,
        "machine_readable_criteria": top_level_criteria,
        "cli_output": cli,
    }
    if status != "done":
        result["open_questions"].append("Plan phase failed. Fix acceptance criteria or task context before implementation.")
    if not plan_data and cli_status != "simulated":
        result["open_questions"].append("CLI output could not be parsed as structured JSON.")
        # Non-simulation: empty plan_data means blocked (P1 false-positive fix)
        status = "blocked"
        result["status"] = status
    if not chunks:
        result["open_questions"].append("No implementation chunks could be generated from the task subtasks.")

    write_with_meta("claude", work_id, result, pathlib.Path(args.out))
    return 0 if status == "done" else 2


def action_run_implement(args: argparse.Namespace) -> int:
    task = load_json(pathlib.Path(args.task))
    task, errors = normalize_task(task)
    if errors:
        return 2

    dispatch = load_json(pathlib.Path(args.dispatch)) if args.dispatch else None
    dispatch_subtasks = (dispatch or {}).get("subtasks", []) if dispatch else []

    subtask: Optional[Dict[str, Any]] = None
    for item in dispatch_subtasks:
        if item.get("subtask_id") == args.subtask_id:
            subtask = item
            break

    if subtask is None:
        for item in task.get("subtasks", []):
            if item.get("subtask_id") == args.subtask_id:
                subtask = item
                break

    if subtask is None:
        logger.error("dispatch/subtask id missing: '%s'", args.subtask_id)
        available = [s.get("subtask_id") for s in dispatch_subtasks] if dispatch_subtasks else [s.get("subtask_id") for s in task.get("subtasks", [])]
        logger.error("Available: %s", available)
        return 1

    if dispatch_subtasks and not any(item.get("subtask_id") == args.subtask_id for item in dispatch_subtasks):
        logger.warning("dispatch does not contain subtask '%s'; falling back to task definition.", args.subtask_id)

    work_id = args.work_id or task.get("task_id", "task-unknown")
    role = normalize_subtask_role(subtask)

    if role == "architect":
        command = os.getenv("CLAUDE_CODE_CMD", "").strip()
        agent_name = "claude"
    else:
        command = os.getenv("CODEX_CLI_CMD", "").strip()
        agent_name = "codex"
    payload = {
        "work_id": work_id,
        "phase": "implement",
        "task_id": task["task_id"],
        "subtask": subtask,
        "full_task": task,
        "request": "Execute implementation for this subtask and include changed files/commands in response payload.",
    }
    cli = run_agent_command(agent_name, command, payload)
    parsed = parse_cli_envelope(cli.get("stdout", ""))
    impl_data = parsed["result"]

    cmd_status = cli.get("status", "failed")
    status = "done" if cmd_status in ("passed", "simulated") else "failed"

    files_changed = impl_data.get("files_changed", []) if isinstance(impl_data.get("files_changed"), list) else []

    result = {
        "status": status,
        "subtask": subtask,
        "role": role,
        "files_changed": files_changed,
        "commands_executed": [{
            "status": cmd_status,
            "command": cli.get("command", ""),
            "return_code": cli.get("return_code", 1),
            "stdout": cli.get("stdout", ""),
            "stderr": cli.get("stderr", ""),
        }],
        "failed_tests": impl_data.get("failed_tests", []) if isinstance(impl_data, dict) else [],
        "artifacts": impl_data.get("artifacts", []) if isinstance(impl_data, dict) else [],
        "cli_output": cli,
        "open_questions": [],
    }
    if not impl_data and cmd_status != "simulated":
        result["open_questions"].append("CLI result payload was not structured JSON (empty or unparsable).")
        # Non-simulation: empty impl_data means blocked (P1 false-positive fix)
        status = "blocked"
        result["status"] = status
    if status == "failed":
        result["open_questions"].append(f"{agent_name} returned status={cmd_status}.")
    write_with_meta(agent_name, work_id, result, pathlib.Path(args.out))
    return 0 if status == "done" else 2


def action_merge_results(args: argparse.Namespace) -> int:
    work_id = args.work_id
    if not work_id:
        return 1

    pattern = pathlib.Path(args.input)
    base = pattern.parent
    results: List[Dict[str, Any]] = []
    lock = None

    if "*" in str(pattern):
        for file in sorted(base.glob(str(pattern.name))):
            if file.name == f"{args.kind}_{work_id}.json":
                continue
            results.append(load_json(file))
    else:
        if pattern.exists():
            results.append(load_json(pattern))

    try:
        lock = acquire_lock(pathlib.Path(args.out))
    except Exception as exc:
        logger.error("unable to acquire merge lock for %s: %s", args.out, exc)
        return 1

    try:
        if not results:
            merged = {
                "status": "blocked",
                "count": 0,
                "subtask_results": [],
                "files_changed": [],
                "commands_executed": [],
                "failed_tests": [],
                "artifacts": [],
                "open_questions": ["No implementation artifacts were produced."],
            }
            write_with_meta("merge", work_id, merged, pathlib.Path(args.out))
            return 2

        status = build_report_status([as_payload(r).get("status", "failed") for r in results])

        expected_subtask_ids: List[str] = []
        dispatch_load_failed = False
        if args.dispatch:
            dispatch_path = pathlib.Path(args.dispatch)
            if dispatch_path.exists():
                try:
                    dispatch_payload = load_json(dispatch_path)
                except Exception as exc:
                    logger.error("failed to load dispatch file '%s': %s", args.dispatch, exc)
                    dispatch_load_failed = True
                else:
                    dispatch_items = dispatch_payload.get("subtasks", [])
                    if isinstance(dispatch_items, list):
                        expected_subtask_ids = [
                            str(item.get("subtask_id"))
                            for item in dispatch_items
                            if isinstance(item, dict) and item.get("subtask_id")
                        ]
            else:
                logger.error("dispatch file not found: '%s'", args.dispatch)
                dispatch_load_failed = True

        result_by_subtask_id: Dict[str, Dict[str, Any]] = {}
        files_changed: List[str] = []
        commands_executed: List[Any] = []
        failed_tests: List[Any] = []
        artifacts: List[Any] = []
        open_questions: List[str] = []
        subtask_results: List[Dict[str, Any]] = []

        for result in results:
            payload = as_payload(result)
            subtask_results.append(payload)
            files_changed.extend(payload.get("files_changed", []) or [])
            commands_executed.extend(payload.get("commands_executed", []) or [])
            failed_tests.extend(payload.get("failed_tests", []) or [])
            artifacts.extend(payload.get("artifacts", []) or [])
            open_questions.extend(payload.get("open_questions", []) or [])
            subtask = payload.get("subtask")
            if isinstance(subtask, dict):
                subtask_id = subtask.get("subtask_id")
                if subtask_id:
                    result_by_subtask_id[str(subtask_id)] = payload

        missing_subtasks: List[str] = []
        for expected in expected_subtask_ids:
            if expected not in result_by_subtask_id:
                missing_subtasks.append(expected)
                open_questions.append(f"Missing implementation result for subtask '{expected}'.")

        if dispatch_load_failed:
            status = "failed"
            open_questions.append(f"Merge requires dispatch file but it could not be loaded: '{args.dispatch}'.")
        elif missing_subtasks and status not in {"failed", "blocked"}:
            status = "failed"

        merged = {
            "status": status,
            "count": len(results),
            "subtask_results": subtask_results,
            "files_changed": sorted({str(x) for x in files_changed}),
            "commands_executed": commands_executed,
            "failed_tests": failed_tests,
            "artifacts": artifacts,
            "open_questions": open_questions,
            "expected_subtasks": expected_subtask_ids,
            "missing_subtasks": missing_subtasks,
        }
        write_with_meta(args.kind, work_id, merged, pathlib.Path(args.out))
        return 0 if status not in {"failed", "blocked"} else 2
    finally:
        if lock:
            release_lock(lock)


def build_junit_xml(test_results: List[Dict[str, Any]], suite_name: str, junit_path: pathlib.Path, total_time: float, failures: int) -> None:
    total = len(test_results)
    lines = [
        f'<testsuite name="{suite_name}" tests="{total}" failures="{failures}" time="{total_time:.3f}">'
    ]
    for index, result in enumerate(test_results, start=1):
        name = f"{suite_name}_{index}"
        lines.append(f'  <testcase classname="{suite_name}" name="{name}" time="{result.get("time_ms", 0)/1000:.3f}">')
        if result.get("status") == "failed":
            lines.append(f'    <failure message="{result.get("command", "command failed").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}"/>')
        lines.append("  </testcase>")
    lines.append("</testsuite>\n")
    ensure_parent(junit_path)
    junit_path.write_text("\n".join(lines), encoding="utf-8")


def action_run_verify(args: argparse.Namespace) -> int:
    commands = parse_verify_commands(os.getenv("VERIFY_COMMANDS", ""))
    work_id = args.work_id
    platform = args.platform

    if args.commands:
        commands = parse_verify_commands(args.commands)

    if not commands:
        config_path = ROOT / "pipeline-config.json"
        if config_path.exists():
            try:
                config = load_json(config_path)
                default_cmds = config.get("default_verify_commands", [])
                if isinstance(default_cmds, list):
                    commands = [str(c).strip() for c in default_cmds if str(c).strip()]
            except Exception:
                pass

    if not commands:
        payload = {
            "platform": platform,
            "status": "failed",
            "commands": [],
            "failed_tests": [],
            "artifacts": [],
            "open_questions": ["VERIFY_COMMANDS not configured — pipeline fail. Set VERIFY_COMMANDS env/arg."],
        }
        out = pathlib.Path(args.out)
        write_with_meta("verify", work_id, payload, out)
        return 1

    command_results: List[Dict[str, Any]] = []
    failed_tests: List[Dict[str, Any]] = []
    failures = 0
    start_total = time.perf_counter()
    cli_timeout = int(os.getenv("CLI_TIMEOUT_SECONDS", "300"))

    for command in commands:
        start = time.perf_counter()
        try:
            if _platform.system() == "Windows":
                proc = subprocess.run(command, shell=True, text=True, capture_output=True, env=os.environ.copy(), timeout=cli_timeout)
            else:
                proc = subprocess.run(shlex.split(command), shell=False, text=True, capture_output=True, env=os.environ.copy(), timeout=cli_timeout)
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            item = {
                "command": command,
                "status": "failed",
                "return_code": -1,
                "time_ms": elapsed_ms,
                "stdout": "",
                "stderr": f"Command timed out after {cli_timeout}s",
            }
            command_results.append(item)
            failures += 1
            failed_tests.append(item)
            continue
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status = "passed" if proc.returncode == 0 else "failed"
        item = {
            "command": command,
            "status": status,
            "return_code": proc.returncode,
            "time_ms": elapsed_ms,
            "stdout": proc.stdout[:6000],
            "stderr": proc.stderr[:3000],
        }
        command_results.append(item)
        if status == "failed":
            failures += 1
            failed_tests.append(item)

    total_time = time.perf_counter() - start_total
    out_path = pathlib.Path(args.out)
    junit_dir = out_path.parent
    junit_path = junit_dir / f"junit_{work_id}_{platform}.xml"
    build_junit_xml(command_results, f"verify-{platform}", junit_path, total_time, failures)

    status = "failed" if failures else "passed"
    payload = {
        "platform": platform,
        "status": status,
        "commands": command_results,
        "failed_tests": failed_tests,
        "artifacts": [str(junit_path.as_posix())],
        "open_questions": [
            item["command"] for item in failed_tests
        ] if failed_tests else [],
    }
    write_with_meta("verify", work_id, payload, pathlib.Path(args.out))
    return 0 if status == "passed" else 2


def action_review(args: argparse.Namespace) -> int:
    work_id = args.work_id

    plan_path = pathlib.Path(args.plan)
    implement_path = pathlib.Path(args.implement)

    plan_payload = as_payload(load_json(plan_path)) if plan_path.exists() else {}
    if implement_path.exists():
        implement_payload = as_payload(load_json(implement_path))
    else:
        implement_payload = {}

    verify_payloads = []
    for verify_path in args.verify:
        path = pathlib.Path(verify_path)
        if path.exists():
            verify_payloads.append(as_payload(load_json(path)))

    open_questions: List[str] = []
    action_required: List[str] = []
    go_no_go = False

    if plan_payload.get("status") != "done":
        go_no_go = True
        action_required.append(f"Plan phase status is '{plan_payload.get('status', 'missing')}', expected 'done'.")

    implement_status = implement_payload.get("status") or "blocked"
    if implement_status != "done":
        go_no_go = True
        action_required.append(f"Implementation status is '{implement_status}'.")

    for verify in verify_payloads:
        if verify.get("status") != "passed":
            go_no_go = True
            action_required.append(f"Verify status is '{verify.get('status', 'missing')}' on {verify.get('platform', 'unknown')} (expected 'passed').")
        open_questions.extend(verify.get("open_questions", []) or [])

    # P1 fix: open_questions from any phase block the merge
    all_open_questions: List[str] = (
        open_questions + action_required
        + plan_payload.get("open_questions", [])
        + implement_payload.get("open_questions", [])
    )
    if all_open_questions and not go_no_go:
        go_no_go = True
        action_required.append(f"Unresolved open questions: {len(all_open_questions)} item(s).")

    review_payload = {
        "work_id": work_id,
        "status": "ready_for_merge" if not go_no_go else "blocked",
        "claude_review": {
            "status": "approved" if not go_no_go else "changes_required",
            "notes": [] if not action_required else ["Check action_required list in this report."],
        },
        "codex_review": {
            "status": "implemented" if implement_status == "done" else "needs_revision",
            "notes": implement_payload.get("open_questions", []),
        },
        "action_required": action_required,
        "open_questions": all_open_questions,
        "go_no_go": go_no_go,
        "references": {
            "plan": str(plan_path),
            "implement": str(implement_path),
            "verify": [str(v.get("platform", "unknown")) for v in verify_payloads],
        },
    }

    write_with_meta("review", work_id, review_payload, pathlib.Path(args.out))

    if go_no_go:
        return 2
    return 0


def action_retrospect(args: argparse.Namespace) -> int:
    review_payload = as_payload(load_json(pathlib.Path(args.review))) if pathlib.Path(args.review).exists() else {}
    work_id = args.work_id

    if not review_payload:
        return 1

    action_required = review_payload.get("action_required", []) or []
    open_questions = review_payload.get("open_questions", []) or []

    next_actions = []
    for index, item in enumerate(action_required[:5], start=1):
        next_actions.append({
            "index": index,
            "type": "rework",
            "title": item,
            "owner": "codex" if "implementation" in item.lower() else "claude",
            "priority": "high",
        })

    if not next_actions and not open_questions:
        next_actions.append({
            "index": 1,
            "type": "observe",
            "title": "No critical issues; run routine quality tuning on next cycle.",
            "owner": "both",
            "priority": "medium",
        })

    payload = {
        "work_id": work_id,
        "generated_at": now_iso(),
        "status": "ready",
        "summary": {
            "go_no_go": review_payload.get("go_no_go", False),
            "issues_count": len(open_questions),
            "next_action_count": len(next_actions),
        },
        "next_plan": next_actions,
        "evidence": {
            "review_reference": pathlib.Path(args.review).as_posix(),
            "questions": open_questions,
        },
    }

    out = pathlib.Path(args.out)
    write_with_meta("retrospect", work_id, payload, out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude+Codex orchestrator")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command")

    validate = sub.add_parser("validate-task")
    validate.add_argument("--task", required=True)
    validate.add_argument("--work-id", default="")
    validate.add_argument("--out", default="")
    validate.set_defaults(func=action_validate_task)

    split = sub.add_parser("split-task")
    split.add_argument("--task", required=True)
    split.add_argument("--plan", default="")
    split.add_argument("--out", required=True)
    split.add_argument("--matrix-output", default="")
    split.set_defaults(func=action_split_task)

    plan = sub.add_parser("run-plan")
    plan.add_argument("--task", required=True)
    plan.add_argument("--work-id", default="")
    plan.add_argument("--out", required=True)
    plan.set_defaults(func=action_run_plan)

    implement = sub.add_parser("run-implement")
    implement.add_argument("--task", required=True)
    implement.add_argument("--dispatch", default="")
    implement.add_argument("--subtask-id", required=True)
    implement.add_argument("--work-id", default="")
    implement.add_argument("--out", required=True)
    implement.set_defaults(func=action_run_implement)

    merge = sub.add_parser("merge-results")
    merge.add_argument("--work-id", required=True)
    merge.add_argument("--kind", required=True)
    merge.add_argument("--input", required=True)
    merge.add_argument("--out", required=True)
    merge.add_argument("--dispatch", default="")
    merge.set_defaults(func=action_merge_results)

    verify = sub.add_parser("run-verify")
    verify.add_argument("--work-id", required=True)
    verify.add_argument("--platform", required=True)
    verify.add_argument("--out", required=True)
    verify.add_argument("--commands", default="")
    verify.set_defaults(func=action_run_verify)

    review = sub.add_parser("run-review")
    review.add_argument("--work-id", required=True)
    review.add_argument("--plan", required=True)
    review.add_argument("--implement", required=True)
    review.add_argument("--verify", nargs="*", default=[])
    review.add_argument("--out", required=True)
    review.set_defaults(func=action_review)

    retrospect = sub.add_parser("run-retrospect")
    retrospect.add_argument("--work-id", required=True)
    retrospect.add_argument("--review", required=True)
    retrospect.add_argument("--out", required=True)
    retrospect.set_defaults(func=action_retrospect)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_usage()
        return 1

    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
