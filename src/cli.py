#!/usr/bin/env python3
"""
Main CLI entry point for srcipts.

This module provides a unified interface to run all available scripts with
their specific dependencies loaded dynamically via uv.
"""

import sys
import subprocess
from pathlib import Path
from typing import List

from registry import get_script, list_scripts as get_all_scripts


def get_script_path(script_name: str) -> Path:
    """Get the path to a script file."""
    return Path(__file__).parent / f"{script_name}.py"


def run_with_uv(script_name: str, script_args: List[str], extras: List[str]) -> int:
    """
    Run a script with uv, installing required dependencies dynamically.

    Args:
        script_name: Name of the script to run
        script_args: Arguments to pass to the script
        extras: List of optional dependency groups to install

    Returns:
        Exit code from the script execution
    """
    script_path = get_script_path(script_name)

    if not script_path.exists():
        print(f"Error: Script '{script_name}' not found at {script_path}", file=sys.stderr)
        return 1

    # Build uv run command with extras
    cmd = ["uv", "run"]

    # Add extras if provided
    if extras:
        for extra in extras:
            cmd.extend(["--extra", extra])

    cmd.extend([str(script_path)] + script_args)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("Error: 'uv' command not found. Please install uv:", file=sys.stderr)
        print("  curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running script: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: srcipts <script-name> [script-args...]", file=sys.stderr)
        print("\nExample: srcipts pixcomp /path/to/images /path/to/output", file=sys.stderr)
        print()
        list_scripts()
        return 1

    script_name = sys.argv[1]
    script_args = sys.argv[2:]

    # Check if it's a help or list command
    if script_name in ["--help", "-h", "help"]:
        list_scripts()
        return 0

    if script_name in ["--list", "-l", "list"]:
        list_scripts()
        return 0

    # Validate script name
    script_config = get_script(script_name)
    if script_config is None:
        print(f"Error: Unknown script '{script_name}'", file=sys.stderr)
        print("\nAvailable scripts:", file=sys.stderr)
        list_scripts()
        return 1

    print(f"Running {script_name}...\n", file=sys.stderr)

    # Run the script with uv
    return run_with_uv(script_name, script_args, script_config.extras)


def list_scripts() -> None:
    """List all available scripts and their descriptions."""
    print("Available scripts:\n")
    for script_config in get_all_scripts():
        print(f"  {script_config.name:<15} - {script_config.description}")
        print(f"  {'Example:':<15}   {script_config.example}")
        print()


if __name__ == "__main__":
    sys.exit(main())
