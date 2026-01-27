"""
Configuration models using Pydantic for type-safe validation.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class TestStatus(str, Enum):
    """Status of a notebook test execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NotebookConfig(BaseModel):
    """Configuration for a single notebook test."""
    name: str
    path: str
    description: str = ""
    timeout_minutes: int = Field(default=30, ge=1, le=120)
    resource_group: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    skip_cells: list[int] = Field(default_factory=list)
    env_vars: dict[str, str] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def validate_path_extension(cls, v: str) -> str:
        if not v.endswith(".ipynb"):
            raise ValueError("Notebook path must end with .ipynb")
        return v


class CleanupConfig(BaseModel):
    """Configuration for Azure resource cleanup."""
    resource_groups: list[str] = Field(default_factory=list)
    purge_cognitive_services: bool = True


class Settings(BaseModel):
    """Global test settings."""
    workspace_root: Path = Path("/workspaces/getting-started-with-foundry")
    output_dir: str = ".test-output"
    default_timeout_minutes: int = 30
    parallel_execution: bool = False
    stop_on_first_failure: bool = False


class TestConfig(BaseModel):
    """Root configuration model."""
    settings: Settings = Field(default_factory=Settings)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    notebooks: list[NotebookConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> TestConfig:
        """Load configuration from YAML file."""
        with open(path) as f:
            return cls(**yaml.safe_load(f))

    def get_notebook(self, name: str) -> NotebookConfig | None:
        """Get notebook config by name."""
        return next((nb for nb in self.notebooks if nb.name == name), None)

    def get_execution_order(self, target: str | None = None) -> list[NotebookConfig]:
        """Get notebooks in dependency-resolved execution order."""
        return self._resolve_deps(target) if target else self._topo_sort()

    def _resolve_deps(self, target: str) -> list[NotebookConfig]:
        """Resolve all dependencies for a target notebook."""
        nb = self.get_notebook(target)
        if not nb:
            raise ValueError(f"Unknown notebook: {target}")

        resolved, visited = [], set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            if cfg := self.get_notebook(name):
                for dep in cfg.depends_on:
                    visit(dep)
                resolved.append(cfg)

        visit(target)
        return resolved

    def _topo_sort(self) -> list[NotebookConfig]:
        """Sort all notebooks by dependencies."""
        result, visited = [], set()

        def visit(nb: NotebookConfig) -> None:
            if nb.name in visited:
                return
            visited.add(nb.name)
            for dep in nb.depends_on:
                if cfg := self.get_notebook(dep):
                    visit(cfg)
            result.append(nb)

        for nb in self.notebooks:
            visit(nb)
        return result


class CellResult(BaseModel):
    """Result of executing a single cell."""
    cell_number: int
    status: TestStatus
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    output: Optional[str] = None


class NotebookResult(BaseModel):
    """Result of executing a notebook."""
    name: str
    status: TestStatus
    duration_seconds: float = 0.0
    cells: list[CellResult] = Field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def passed_cells(self) -> int:
        return sum(1 for c in self.cells if c.status == TestStatus.PASSED)

    @property
    def failed_cells(self) -> int:
        return sum(1 for c in self.cells if c.status == TestStatus.FAILED)

    @property
    def skipped_cells(self) -> int:
        return sum(1 for c in self.cells if c.status == TestStatus.SKIPPED)


class TestSuiteResult(BaseModel):
    """Result of the entire test suite."""
    status: TestStatus = TestStatus.PENDING
    duration_seconds: float = 0.0
    notebooks: list[NotebookResult] = Field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for n in self.notebooks if n.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for n in self.notebooks if n.status == TestStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for n in self.notebooks if n.status == TestStatus.SKIPPED)
