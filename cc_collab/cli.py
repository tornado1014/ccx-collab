"""cc-collab CLI entry point."""
import click

from cc_collab import __version__
from cc_collab.bridge import setup_simulate_mode


@click.group()
@click.version_option(version=__version__, prog_name="cc-collab")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--simulate", is_flag=True, help="Run in simulation mode (no real CLI calls)")
@click.pass_context
def cli(ctx, verbose, simulate):
    """cc-collab: Claude Code + Codex CLI collaboration pipeline tool."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["simulate"] = simulate
    if simulate:
        setup_simulate_mode(True)
    if verbose:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )


# Register stage commands
from cc_collab.commands.stages import (
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
from cc_collab.commands.tools import health, cleanup, init
cli.add_command(health)
cli.add_command(cleanup)
cli.add_command(init)

# Register pipeline commands
from cc_collab.commands.pipeline import run, status
cli.add_command(run)
cli.add_command(status)


def main():
    cli()


if __name__ == "__main__":
    main()
