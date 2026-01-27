"""
Azure resource cleanup utilities.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
from typing import Any

from rich.console import Console
from rich.panel import Panel

from .models import TestConfig

console = Console()


def _az_json(args: list[str], timeout: int = 60) -> list[dict[str, Any]]:
    """Run az CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["az", *args, "-o", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else []
    except Exception:
        return []


class AzureCleanup:
    """Cleans up Azure resources created during tests."""

    def __init__(self, config: TestConfig):
        self.config = config

    def run(self, dry_run: bool = False) -> None:
        """Execute full cleanup."""
        console.print()
        console.print(Panel.fit("[bold]Azure Resource Cleanup[/bold]", border_style="yellow"))
        console.print()

        if self.config.cleanup.purge_cognitive_services:
            self._purge_cognitive_services(dry_run)

        self._delete_resource_groups(dry_run)

        console.print()
        msg = "[yellow]Dry run complete. No resources deleted.[/yellow]" if dry_run else "[green]Cleanup complete.[/green]"
        console.print(msg)

    def list_resources(self) -> None:
        """List resources that would be cleaned up."""
        console.print()
        console.print(Panel.fit("[bold]Resources to Clean Up[/bold]", border_style="blue"))

        console.print("\n[bold]Resource Groups:[/bold]")
        if rgs := self._get_matching_resource_groups():
            for rg in rgs:
                console.print(f"  - {rg}")
        else:
            console.print("  [dim]No matching resource groups[/dim]")

        console.print("\n[bold]Soft-Deleted Cognitive Services:[/bold]")
        deleted = _az_json(["cognitiveservices", "account", "list-deleted", "--query", "[].{name:name, location:location}"])
        if deleted:
            for acc in deleted:
                console.print(f"  - {acc['name']} ({acc['location']})")
        else:
            console.print("  [dim]None[/dim]")

    def _get_matching_resource_groups(self) -> list[str]:
        """Get existing resource groups matching configured patterns."""
        all_rgs = _az_json(["group", "list", "--query", "[].name"], timeout=30)
        if not all_rgs:
            return []

        matching = []
        for pattern in self.config.cleanup.resource_groups:
            for rg in all_rgs:
                if fnmatch.fnmatch(rg, pattern) and rg not in matching:
                    matching.append(rg)
        return matching

    def _delete_resource_groups(self, dry_run: bool) -> None:
        """Delete resource groups matching patterns."""
        rgs = self._get_matching_resource_groups()
        if not rgs:
            console.print("  [dim]No matching resource groups found[/dim]")
            return

        console.print(f"  [bold]Resource groups to delete ({len(rgs)}):[/bold]")

        for rg in rgs:
            if dry_run:
                console.print(f"    [yellow]Would delete:[/yellow] {rg}")
            else:
                console.print(f"    [red]Deleting:[/red] {rg}...", end=" ")
                try:
                    subprocess.run(["az", "group", "delete", "-n", rg, "--yes", "--no-wait"], capture_output=True, timeout=60)
                    console.print("[green]queued[/green]")
                except Exception as e:
                    console.print(f"[red]failed: {e}[/red]")

    def _purge_cognitive_services(self, dry_run: bool) -> None:
        """Purge soft-deleted Cognitive Services accounts."""
        console.print("  [bold]Checking for soft-deleted Cognitive Services...[/bold]")

        deleted = _az_json(["cognitiveservices", "account", "list-deleted"])
        if not deleted:
            console.print("    [dim]No soft-deleted accounts found[/dim]")
            return

        console.print(f"    Found {len(deleted)} soft-deleted account(s)")

        for account in deleted:
            name = account.get("name", "unknown")
            resource_id = account.get("id", "")

            if dry_run:
                console.print(f"    [yellow]Would purge:[/yellow] {name}")
            else:
                console.print(f"    [red]Purging:[/red] {name}...", end=" ")
                try:
                    subprocess.run(["az", "cognitiveservices", "account", "purge", "--id", resource_id], capture_output=True, timeout=120)
                    console.print("[green]done[/green]")
                except Exception as e:
                    console.print(f"[red]failed: {e}[/red]")
