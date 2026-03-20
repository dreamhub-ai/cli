"""dh update — self-update and version check notifications."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time

import httpx
import typer

from dreamhubcli import __version__
from dreamhubcli.output import console, print_error, print_success, print_warning

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = "https://api.github.com/repos/dreamhub-ai/cli/releases/latest"
_VERSION_CHECK_INTERVAL_SECONDS = 86400  # 24 hours


def _parse_version(version_string: str) -> tuple[int, ...]:
    """Parse a version string like '1.2.0' or 'v1.2.0' into an int tuple."""
    cleaned = version_string.lstrip("v").strip()
    return tuple(int(part) for part in cleaned.split("."))


def _is_pipx_install() -> bool:
    """Check if dreamhubcli was installed via pipx."""
    pipx_path = shutil.which("pipx")
    if not pipx_path:
        return False
    try:
        result = subprocess.run(
            [pipx_path, "list", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "dreamhubcli" in result.stdout
    except Exception:
        return False


def update_command() -> None:
    """Update Dreamhub CLI to the latest version."""
    console.print(f"[dim]Current version: {__version__}[/dim]")

    if _is_pipx_install():
        console.print("[dim]Detected pipx installation. Running: pipx upgrade dreamhubcli[/dim]")
        try:
            result = subprocess.run(
                [shutil.which("pipx") or "pipx", "upgrade", "dreamhubcli"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                # Extract new version from pipx output
                console.print(result.stdout.strip())
                print_success("Update complete.")
            else:
                print_error(f"pipx upgrade failed:\n{result.stderr.strip()}")
                raise typer.Exit(code=1)
        except subprocess.TimeoutExpired:
            print_error("Update timed out.")
            raise typer.Exit(code=1)
    else:
        pip_path = shutil.which("pip") or shutil.which("pip3")
        if not pip_path:
            print_error("Neither pipx nor pip found. Install manually.")
            raise typer.Exit(code=1)
        console.print("[dim]Running: pip install --upgrade git+https://github.com/dreamhub-ai/cli.git[/dim]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "git+https://github.com/dreamhub-ai/cli.git"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print_success("Update complete.")
            else:
                print_error(f"pip install failed:\n{result.stderr.strip()}")
                raise typer.Exit(code=1)
        except subprocess.TimeoutExpired:
            print_error("Update timed out.")
            raise typer.Exit(code=1)

    console.print("[dim]Restart your shell or run 'dh --version' to verify.[/dim]")


def check_for_update_notice() -> None:
    """Print a notice to stderr if a newer version is available. Runs at most once per 24h."""
    from dreamhubcli.config import load_config, save_config

    config = load_config()

    if config.last_version_check:
        try:
            last_check = time.mktime(time.strptime(config.last_version_check, "%Y-%m-%dT%H:%M:%SZ"))
            if time.time() - last_check < _VERSION_CHECK_INTERVAL_SECONDS:
                # Still within the check interval — show cached notice if applicable
                if config.latest_known_version:
                    try:
                        if _parse_version(config.latest_known_version) > _parse_version(__version__):
                            print_warning(
                                f"Update available: {__version__} -> {config.latest_known_version}. Run: dh update"
                            )
                    except (ValueError, TypeError):
                        pass
                return
        except (ValueError, OverflowError):
            pass

    try:
        response = httpx.get(GITHUB_RELEASES_URL, timeout=5.0, follow_redirects=True)
        if response.status_code != 200:
            return
        body = response.json()
        tag_name = body.get("tag_name", "")
        latest_version = tag_name.lstrip("v").strip()
        if not latest_version:
            return

        config.latest_known_version = latest_version
        config.last_version_check = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_config(config)

        if _parse_version(latest_version) > _parse_version(__version__):
            print_warning(f"Update available: {__version__} -> {latest_version}. Run: dh update")
    except Exception:
        logger.debug("Version check failed", exc_info=True)
