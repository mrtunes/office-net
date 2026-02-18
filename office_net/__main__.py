"""Allow running as `python -m office_net` or via the `office-net` command."""

import sys


def main() -> None:
    """Entry point for both `python -m office_net` and the `office-net` console script."""
    if len(sys.argv) <= 1:
        # No command given - launch interactive menu
        from office_net.interactive import run
        run()
    else:
        # CLI command given - use typer
        from office_net.cli import app
        app()


if __name__ == "__main__":
    main()
