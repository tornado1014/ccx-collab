"""Rich-based output helpers for ccx-collab CLI."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)

console = Console()


def print_header(title: str) -> None:
    """Print a styled header panel."""
    logger.debug("Header: %s", title)
    console.print(Panel(f"[bold]{title}[/bold]", style="cyan"))


def print_stage_result(stage: str, exit_code: int, output_path: str = "") -> None:
    """Show stage completion with status icon."""
    logger.debug("Stage result: stage=%s, exit_code=%d, output_path=%s",
                 stage, exit_code, output_path)
    if exit_code == 0:
        icon = "[green]✓[/green]"
        status = "[green]passed[/green]"
    else:
        icon = "[red]✗[/red]"
        status = f"[red]failed (exit {exit_code})[/red]"
    msg = f"{icon} {stage}: {status}"
    if output_path:
        msg += f" → {output_path}"
    console.print(msg)


def print_pipeline_header(task: str, work_id: str, mode: str) -> None:
    """Show pipeline start banner."""
    table = Table(show_header=False, box=None)
    table.add_row("[bold]Task[/bold]", task)
    table.add_row("[bold]Work ID[/bold]", work_id)
    table.add_row("[bold]Mode[/bold]", mode)
    console.print(Panel(table, title="[bold cyan]Pipeline Runner[/bold cyan]"))


def print_error(message: str) -> None:
    """Print red error message."""
    logger.debug("Error output: %s", message)
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print green success message."""
    console.print(f"[green]✓[/green] {message}")


def print_json_result(data: Dict[str, Any]) -> None:
    """Pretty-print JSON result."""
    console.print_json(json.dumps(data, indent=2, ensure_ascii=False))
