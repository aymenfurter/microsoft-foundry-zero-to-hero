"""
Test execution engine with rich console output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from .extractor import NotebookExtractor
from .models import NotebookConfig, NotebookResult, TestConfig, TestStatus, TestSuiteResult

console = Console()

# Progress bar configuration
PROGRESS_COLUMNS = (
    SpinnerColumn(),
    TextColumn("[bold blue]{task.description}"),
    BarColumn(),
    TimeElapsedColumn(),
)


class TestRunner:
    """Executes notebook tests with rich progress display."""

    def __init__(self, config: TestConfig):
        self.config = config
        self.output_dir = config.settings.workspace_root / config.settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._deps_installed = False

    def run_all(self, target: str | None = None) -> TestSuiteResult:
        """Run all notebooks (or dependencies of target)."""
        return self._execute(self.config.get_execution_order(target))

    def run_notebook(self, name: str) -> TestSuiteResult:
        """Run a single notebook by name (with dependencies)."""
        return self._execute(self.config.get_execution_order(name))

    def _execute(self, notebooks: list[NotebookConfig]) -> TestSuiteResult:
        """Core execution loop for notebook tests."""
        self._ensure_dependencies()
        result = TestSuiteResult()
        start = time.perf_counter()

        self._print_header(len(notebooks))

        with Progress(*PROGRESS_COLUMNS, console=console) as progress:
            task = progress.add_task("Running", total=len(notebooks))

            for nb in notebooks:
                progress.update(task, description=f"[bold blue]{nb.name}")
                nb_result = self._run_notebook(nb)
                result.notebooks.append(nb_result)
                progress.advance(task)

                self._print_result(nb_result)

                if nb_result.status == TestStatus.FAILED and self.config.settings.stop_on_first_failure:
                    break

        result.duration_seconds = time.perf_counter() - start
        result.status = TestStatus.PASSED if result.failed == 0 else TestStatus.FAILED
        self._print_summary(result)
        return result

    def _run_notebook(self, nb: NotebookConfig) -> NotebookResult:
        """Execute a single notebook's generated script."""
        start = time.perf_counter()
        notebook_path = self.config.settings.workspace_root / nb.path
        script_dir = self.output_dir / nb.name

        try:
            # Generate executable script
            script_path = script_dir / f"{nb.name.replace('-', '_')}.py"
            NotebookExtractor(notebook_path).save_script(script_path, nb.skip_cells)

            # Copy helper modules
            for py_file in notebook_path.parent.glob("*.py"):
                if py_file.name != "__init__.py":
                    shutil.copy2(py_file, script_dir / py_file.name)

            # Build environment
            env = {
                **os.environ,
                **nb.env_vars,
                "PYTHONPATH": f"{script_dir}:{notebook_path.parent}:{os.environ.get('PYTHONPATH', '')}",
            }

            # Execute
            proc = subprocess.run(
                ["python", str(script_path)],
                capture_output=True,
                text=True,
                timeout=nb.timeout_minutes * 60,
                env=env,
                cwd=notebook_path.parent,
            )

            # Save logs
            (script_dir / "stdout.log").write_text(proc.stdout)
            (script_dir / "stderr.log").write_text(proc.stderr)

            if proc.returncode == 0:
                return NotebookResult(
                    name=nb.name,
                    status=TestStatus.PASSED,
                    duration_seconds=time.perf_counter() - start,
                )

            return NotebookResult(
                name=nb.name,
                status=TestStatus.FAILED,
                duration_seconds=time.perf_counter() - start,
                error_message=proc.stderr or proc.stdout,
            )

        except subprocess.TimeoutExpired:
            return NotebookResult(
                name=nb.name,
                status=TestStatus.FAILED,
                duration_seconds=time.perf_counter() - start,
                error_message=f"Timeout after {nb.timeout_minutes} minutes",
            )
        except Exception as e:
            return NotebookResult(
                name=nb.name,
                status=TestStatus.FAILED,
                duration_seconds=time.perf_counter() - start,
                error_message=str(e),
            )

    def _ensure_dependencies(self) -> None:
        """Install test dependencies once per session."""
        if self._deps_installed:
            return

        req_file = Path(__file__).parent / "requirements.txt"
        if not req_file.exists():
            return

        console.print("[dim]Installing test dependencies...[/dim]")
        result = subprocess.run(
            ["pip", "install", "-q", "-r", str(req_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[yellow]Warning: {result.stderr}[/yellow]")

        self._deps_installed = True

    def _print_header(self, count: int) -> None:
        """Print test run header."""
        console.print()
        console.print(Panel.fit(
            f"[bold]Foundry Workshop Test Suite[/bold]\n[dim]Running {count} notebook(s)[/dim]",
            border_style="blue",
        ))
        console.print()

    def _print_result(self, result: NotebookResult) -> None:
        """Print single notebook result."""
        if result.status == TestStatus.PASSED:
            console.print(f"  [green]✓[/green] {result.name}")
        else:
            console.print(f"  [red]✗[/red] {result.name}")
            if result.error_message:
                for line in result.error_message.strip().splitlines()[-10:]:
                    console.print(f"    [dim red]{line}[/dim red]")

    def _print_summary(self, result: TestSuiteResult) -> None:
        """Print test summary table."""
        console.print()

        table = Table(title="Test Results", show_header=True, header_style="bold")
        table.add_column("Notebook", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")

        for nb in result.notebooks:
            passed = nb.status == TestStatus.PASSED
            table.add_row(
                nb.name,
                Text(f"{'✓' if passed else '✗'} {nb.status.value}", style="green" if passed else "red"),
                f"{nb.duration_seconds:.1f}s",
            )

        console.print(table)
        console.print()

        if result.status == TestStatus.PASSED:
            console.print(Panel(
                f"[bold green]All {result.passed} tests passed[/bold green] in {result.duration_seconds:.1f}s",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[bold red]{result.failed} of {len(result.notebooks)} tests failed[/bold red] in {result.duration_seconds:.1f}s",
                border_style="red",
            ))
