from __future__ import annotations

import os

from rich.console import Console
from rich.markup import escape

# Check environment variable to determine ANSI color support
no_color = bool(os.getenv("NO_COLOR"))

# Create a console object with or without color support
console = Console(color_system=None if no_color else "auto")
err_console = Console(color_system=None if no_color else "auto", stderr=True)


def print_success(message: str) -> None:
    """Prints a message indicating success in green color."""
    console.print(f"[bold green]{escape(message)}[/bold green]")


def print_error(message: str) -> None:
    """Prints a message indicating an error in red color."""
    err_console.print(f"[bold red]{escape(message)}[/bold red]")


def print_info(message: str) -> None:
    """Prints an informational message in blue color."""
    console.print(f"[bold blue]{escape(message)}[/bold blue]")
