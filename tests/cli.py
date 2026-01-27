"""
Modern CLI using Typer with rich output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .cleanup import AzureCleanup
from .models import TestConfig
from .reports import ReportGenerator
from .runner import TestRunner

app = typer.Typer(
    name="tests",
    help="Foundry Workshop Notebook Testing Framework",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
CONFIG_PATH = Path(__file__).parent / "notebooks.yaml"


def load_config() -> TestConfig:
    """Load test configuration."""
    if not CONFIG_PATH.exists():
        console.print(f"[red]Config not found: {CONFIG_PATH}[/red]")
        raise typer.Exit(1)
    return TestConfig.from_yaml(CONFIG_PATH)


@app.command()
def run(
    notebook: Optional[str] = typer.Option(None, "--notebook", "-n", help="Run specific notebook (includes dependencies)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed without running"),
    report: Optional[str] = typer.Option(None, "--report", "-r", help="Generate report (junit, markdown, html)"),
) -> None:
    """Run notebook tests."""
    config = load_config()

    if dry_run:
        notebooks = config.get_execution_order(notebook)
        console.print()
        console.print(Panel.fit("[bold]Dry Run - Execution Plan[/bold]", border_style="yellow"))
        console.print()
        for i, nb in enumerate(notebooks, 1):
            deps = f" (depends on: {', '.join(nb.depends_on)})" if nb.depends_on else ""
            console.print(f"  {i}. [cyan]{nb.name}[/cyan]{deps}")
            console.print(f"     [dim]{nb.description}[/dim]")
        console.print()
        return

    runner = TestRunner(config)
    suite_result = runner.run_notebook(notebook) if notebook else runner.run_all()

    if report:
        generator = ReportGenerator(config)
        generators = {"junit": generator.generate_junit, "markdown": generator.generate_markdown, "html": generator.generate_html}
        if report not in generators:
            console.print(f"[red]Unknown report format: {report}[/red]")
            raise typer.Exit(1)
        path = generators[report](suite_result)
        console.print(f"\n[green]Report saved:[/green] {path}")

    raise typer.Exit(1 if suite_result.failed > 0 else 0)


@app.command("list")
def list_notebooks(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info")) -> None:
    """List available notebook tests."""
    config = load_config()

    console.print()
    console.print(Panel.fit("[bold]Available Notebook Tests[/bold]", border_style="blue"))
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Timeout", justify="right")
    if verbose:
        table.add_column("Dependencies")
        table.add_column("Resource Group")

    for nb in config.notebooks:
        row = [nb.name, nb.description or "-", f"{nb.timeout_minutes}m"]
        if verbose:
            row.extend([", ".join(nb.depends_on) or "-", nb.resource_group or "-"])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(config.notebooks)} notebooks[/dim]")


@app.command()
def cleanup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted without deleting"),
    list_only: bool = typer.Option(False, "--list", "-l", help="Only list resources, don't delete"),
) -> None:
    """Clean up Azure resources created during tests."""
    cleaner = AzureCleanup(load_config())
    cleaner.list_resources() if list_only else cleaner.run(dry_run=dry_run)


@app.command()
def extract(
    notebook: str = typer.Argument(..., help="Notebook name to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path for extracted script"),
) -> None:
    """Extract notebook to executable Python script."""
    config = load_config()
    nb_config = config.get_notebook(notebook)

    if not nb_config:
        console.print(f"[red]Unknown notebook: {notebook}[/red]")
        raise typer.Exit(1)

    from .extractor import NotebookExtractor

    notebook_path = config.settings.workspace_root / nb_config.path
    output_path = output or config.settings.workspace_root / config.settings.output_dir / notebook / f"{notebook.replace('-', '_')}.py"

    NotebookExtractor(notebook_path).save_script(output_path, nb_config.skip_cells)
    console.print(f"[green]Extracted:[/green] {output_path}")


@app.command()
def info() -> None:
    """Show configuration and environment info."""
    import subprocess

    config = load_config()

    console.print()
    console.print(Panel.fit("[bold]Test Framework Configuration[/bold]", border_style="blue"))

    console.print("\n[bold]Settings:[/bold]")
    console.print(f"  Workspace: {config.settings.workspace_root}")
    console.print(f"  Output dir: {config.settings.output_dir}")
    console.print(f"  Default timeout: {config.settings.default_timeout_minutes}m")

    console.print(f"\n[bold]Notebooks:[/bold] {len(config.notebooks)}")
    console.print(f"[bold]Cleanup patterns:[/bold] {len(config.cleanup.resource_groups)}")

    try:
        result = subprocess.run(["az", "account", "show", "--query", "name", "-o", "tsv"], capture_output=True, text=True, timeout=10)
        status = f"[green]Logged in as {result.stdout.strip()}[/green]" if result.returncode == 0 else "[yellow]Not logged in[/yellow]"
    except Exception:
        status = "[red]Not available[/red]"
    console.print(f"\n[bold]Azure CLI:[/bold] {status}")


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
