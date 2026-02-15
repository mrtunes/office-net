"""Allow running as `python -m office_net`."""

import sys

if len(sys.argv) <= 1:
    # No command given - launch interactive menu
    from office_net.interactive import run
    run()
else:
    # CLI command given - use typer
    from office_net.cli import app
    app()
