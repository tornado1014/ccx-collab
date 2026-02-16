"""ccx-collab CLI entry point."""
import logging

import click

from ccx_collab import __version__
from ccx_collab.bridge import setup_simulate_mode
from ccx_collab.config import load_ccx_collab_config

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="ccx-collab")
@click.option("--verbose", "-v", is_flag=True, default=None, help="Enable verbose output")
@click.option("--simulate", is_flag=True, default=None, help="Run in simulation mode (no real CLI calls)")
@click.pass_context
def cli(ctx, verbose, simulate):
    """ccx-collab: Claude Code + Codex CLI collaboration pipeline tool."""
    ctx.ensure_object(dict)

    # Build CLI overrides from explicitly-provided flags.
    # Click sets is_flag options to None when not provided (due to default=None).
    cli_overrides = {}
    if verbose is not None:
        cli_overrides["verbose"] = verbose
    if simulate is not None:
        cli_overrides["simulate"] = simulate

    # Load and merge configuration: CLI > project > user > defaults
    config = load_ccx_collab_config(cli_overrides=cli_overrides)
    ctx.obj.update(config)

    # Configure root logger based on effective verbose setting
    if config.get("verbose"):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logger.debug("Verbose logging enabled")
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(levelname)s: %(message)s",
        )

    if config.get("simulate"):
        setup_simulate_mode(True)
        logger.debug("Simulation mode activated")


# Register stage commands
from ccx_collab.commands.stages import (
    validate, plan, split, implement, merge, verify, review, retrospect,
)
cli.add_command(validate)
cli.add_command(plan)
cli.add_command(split)
cli.add_command(implement)
cli.add_command(merge)
cli.add_command(verify)
cli.add_command(review)
cli.add_command(retrospect)

# Register tool commands
from ccx_collab.commands.tools import health, cleanup, init, web
cli.add_command(health)
cli.add_command(cleanup)
cli.add_command(init)
cli.add_command(web)

# Register pipeline commands
from ccx_collab.commands.pipeline import run, status
cli.add_command(run)
cli.add_command(status)


def main():
    cli()


if __name__ == "__main__":
    main()
