"""Mermaid pipeline diagram generation."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["validate", "plan", "split", "implement", "merge", "verify", "review"]

# Mermaid style classes for different statuses
STYLE_MAP = {
    "completed": "fill:#2ecc71,stroke:#27ae60,color:white",
    "passed": "fill:#2ecc71,stroke:#27ae60,color:white",
    "ready": "fill:#2ecc71,stroke:#27ae60,color:white",
    "done": "fill:#2ecc71,stroke:#27ae60,color:white",
    "running": "fill:#3498db,stroke:#2980b9,color:white",
    "failed": "fill:#e74c3c,stroke:#c0392b,color:white",
    "pending": "fill:#95a5a6,stroke:#7f8c8d,color:white",
    "skipped": "fill:#f39c12,stroke:#e67e22,color:white",
}

STAGE_LABELS = {
    "validate": "Validate Task",
    "plan": "Plan (Claude)",
    "split": "Split Subtasks",
    "implement": "Implement",
    "merge": "Merge Results",
    "verify": "Verify",
    "review": "Review",
}


def _status_class(status: str) -> str:
    """Return the Mermaid class name for a status."""
    if status in ("completed", "passed", "ready", "done"):
        return "completed"
    if status in ("running",):
        return "running"
    if status in ("failed",):
        return "failed"
    if status in ("skipped",):
        return "skipped"
    return "pending"


def generate_pipeline_diagram(
    stage_statuses: Dict[str, str],
    subtask_ids: Optional[List[str]] = None,
) -> str:
    """Generate a Mermaid flowchart for the pipeline.

    Args:
        stage_statuses: dict mapping stage name -> status string
        subtask_ids: optional list of subtask IDs for parallel visualization

    Returns:
        Mermaid markdown string
    """
    lines = ["graph TD"]

    # Define style classes (skip aliases)
    for cls_name, style in STYLE_MAP.items():
        if cls_name in ("passed", "ready", "done"):
            continue
        lines.append(f"    classDef {cls_name} {style}")

    # Create nodes for each stage
    for i, stage in enumerate(PIPELINE_STAGES):
        label = STAGE_LABELS.get(stage, stage.title())
        status = stage_statuses.get(stage, "pending")
        cls = _status_class(status)

        if stage == "implement" and subtask_ids:
            # Show parallel subtasks
            lines.append(f"    {stage}[{label}]:::{cls}")
            for j, st_id in enumerate(subtask_ids):
                sub_status = stage_statuses.get(f"implement_{st_id}", status)
                sub_cls = _status_class(sub_status)
                lines.append(f"    sub{j}[\"{st_id}\"]:::{sub_cls}")
                lines.append(f"    {stage} --> sub{j}")
            # Connect subtasks to next stage (merge)
            next_stage = PIPELINE_STAGES[i + 1] if i + 1 < len(PIPELINE_STAGES) else None
            if next_stage:
                for j in range(len(subtask_ids)):
                    lines.append(f"    sub{j} --> {next_stage}")
        else:
            lines.append(f"    {stage}[{label}]:::{cls}")

    # Create sequential edges (skip implement->merge if subtasks handled it)
    for i in range(len(PIPELINE_STAGES) - 1):
        curr = PIPELINE_STAGES[i]
        nxt = PIPELINE_STAGES[i + 1]
        if curr == "implement" and subtask_ids:
            continue  # Already connected via subtasks
        if curr == "split" and subtask_ids:
            # split connects to implement (the parent node), which fans out
            lines.append(f"    {curr} --> {nxt}")
            continue
        lines.append(f"    {curr} --> {nxt}")

    return "\n".join(lines)


def generate_pipeline_diagram_from_stages(stages: list) -> str:
    """Generate diagram from a list of StageResult objects or dicts."""
    stage_statuses: Dict[str, str] = {}
    for s in stages:
        name = s.stage_name if hasattr(s, "stage_name") else s.get("stage_name", "")
        status = s.status if hasattr(s, "status") else s.get("status", "pending")
        if name:
            stage_statuses[name] = status
    return generate_pipeline_diagram(stage_statuses)


def generate_pipeline_diagram_from_results(
    work_id: str, results_dir: str = "agent/results"
) -> str:
    """Generate diagram by scanning result files in the results directory."""
    results = Path(results_dir)
    stage_statuses: Dict[str, str] = {}
    subtask_ids: List[str] = []

    prefix_map = {
        "validation": "validate",
        "plan": "plan",
        "dispatch": "split",
        "implement": "implement",
        "verify": "verify",
        "review": "review",
    }

    if not results.is_dir():
        return generate_pipeline_diagram({})

    for f in results.glob(f"*_{work_id}*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            status = data.get("status", "unknown")

            # Determine stage from filename prefix
            stem = f.stem
            for prefix, stage_name in prefix_map.items():
                if stem.startswith(prefix):
                    # Check for subtask implementations
                    subtask_marker = f"implement_{work_id}_"
                    if stage_name == "implement" and subtask_marker in stem:
                        subtask_id = stem.split(subtask_marker)[-1]
                        if subtask_id:
                            subtask_ids.append(subtask_id)
                            stage_statuses[f"implement_{subtask_id}"] = status
                    else:
                        stage_statuses[stage_name] = status
                    break
        except (json.JSONDecodeError, OSError):
            continue

    return generate_pipeline_diagram(
        stage_statuses, subtask_ids if subtask_ids else None
    )
