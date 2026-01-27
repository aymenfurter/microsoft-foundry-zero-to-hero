"""
Notebook extraction and transformation.

Extracts code cells from Jupyter notebooks and transforms them into
executable Python scripts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Regex patterns for cell transformations
RE_WRITEFILE = re.compile(r"^%%writefile\s+(.+)\n", re.MULTILINE)
RE_BASH = re.compile(r"^%%bash(\s+-s\s+(.+))?\s*\n", re.MULTILINE)
RE_VAR_INTERPOLATION = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
RE_BASH_ARGS = re.compile(r"\$\{?(\w+)\}?")

SCRIPT_HEADER = '''#!/usr/bin/env python3
"""Auto-generated test script from: {name}"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

os.chdir("{working_dir}")

'''


@dataclass(frozen=True, slots=True)
class Cell:
    """Represents a notebook code cell."""
    number: int
    source: str
    cell_type: str

    @property
    def is_code(self) -> bool:
        return self.cell_type == "code"

    @property
    def is_empty(self) -> bool:
        return not self.source.strip()

    @property
    def is_commented(self) -> bool:
        """Check if all non-empty lines are comments."""
        lines = [line for line in self.source.strip().splitlines() if line.strip()]
        return not lines or all(line.strip().startswith("#") for line in lines)

    @property
    def is_executable(self) -> bool:
        """Check if cell should be executed."""
        return self.is_code and not self.is_empty and not self.is_commented


class NotebookExtractor:
    """Extracts and transforms notebook cells into executable Python."""

    def __init__(self, notebook_path: Path):
        self.notebook_path = notebook_path
        self.working_dir = notebook_path.parent
        self._helper_counter = 0

    def extract_cells(self) -> Iterator[Cell]:
        """Yield all cells from the notebook."""
        with open(self.notebook_path, encoding="utf-8") as f:
            nb = json.load(f)

        for i, cell in enumerate(nb.get("cells", []), start=1):
            yield Cell(
                number=i,
                source="".join(cell.get("source", [])),
                cell_type=cell.get("cell_type", ""),
            )

    def extract_code_cells(self, skip_cells: list[int] | None = None) -> Iterator[Cell]:
        """Yield executable code cells, optionally skipping specified cells."""
        skip = set(skip_cells or [])
        for cell in self.extract_cells():
            if cell.is_executable and cell.number not in skip:
                yield cell

    def transform_cell(self, cell: Cell) -> str:
        """Transform a cell's source code into executable Python."""
        code = cell.source

        # Handle %%writefile magic
        if match := RE_WRITEFILE.match(code):
            return self._gen_writefile(match.group(1).strip(), code[match.end() :])

        # Handle %%bash magic
        if match := RE_BASH.match(code):
            return self._gen_bash(code[match.end() :], match.group(2))

        # Transform shell commands (! and %)
        code = self._transform_shell_commands(code)

        # Transform top-level async constructs
        if self._has_top_level_async(code):
            code = self._transform_async_code(code)

        return code

    # --- Shell Command Transformation ---

    def _transform_shell_commands(self, code: str) -> str:
        """Transform !cmd and %pip commands to subprocess calls."""
        lines = code.splitlines()
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith(("!", "%pip")):
                indent = line[: len(line) - len(line.lstrip())]
                cmd, i = self._collect_shell_command(lines, i, stripped)
                result.append(self._gen_subprocess(cmd, indent))
            else:
                result.append(line)
            i += 1

        return "\n".join(result)

    def _collect_shell_command(self, lines: list[str], start: int, first_line: str) -> tuple[str, int]:
        """Collect shell command including backslash continuations."""
        cmd_parts = [first_line[1:]]  # Remove ! or %
        i = start

        while cmd_parts[-1].rstrip().endswith("\\") and i + 1 < len(lines):
            cmd_parts[-1] = cmd_parts[-1].rstrip()[:-1]
            i += 1
            cmd_parts.append(lines[i].strip())

        return " ".join(cmd_parts), i

    # --- Code Generators ---

    def _gen_subprocess(self, cmd: str, indent: str = "") -> str:
        """Generate subprocess.run() call for a shell command."""
        if RE_VAR_INTERPOLATION.search(cmd):
            return f'{indent}subprocess.run(f"""{cmd}""", shell=True, check=True)'
        escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
        return f'{indent}subprocess.run("{escaped}", shell=True, check=True)'

    def _gen_writefile(self, filename: str, content: str) -> str:
        """Generate code to write a file."""
        escaped = content.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        return f'''import os
os.makedirs(os.path.dirname("{filename}") or ".", exist_ok=True)
with open("{filename}", "w") as _f:
    _f.write("""{escaped}""")
print(f"Written: {filename}")'''

    def _gen_bash(self, bash_code: str, args_str: str | None) -> str:
        """Generate subprocess call for %%bash block."""
        if args_str:
            # Replace $1, $2, etc. with Python variable interpolation
            for i, arg in enumerate(RE_BASH_ARGS.findall(args_str), 1):
                bash_code = bash_code.replace(f"${i}", "{" + arg + "}")
            return f'subprocess.run(f"""{bash_code}""", shell=True, check=True)'

        prefix = "f" if RE_VAR_INTERPOLATION.search(bash_code) else ""
        return f'subprocess.run({prefix}"""{bash_code}""", shell=True, check=True)'

    # --- Async Transformation ---

    def _has_top_level_async(self, code: str) -> bool:
        """Check if code has top-level async constructs."""
        for line in code.splitlines():
            if line and not line[0].isspace():
                stripped = line.strip()
                if stripped.startswith("await ") or " = await " in stripped or stripped.startswith("async for "):
                    return True
        return False

    def _transform_async_code(self, code: str) -> str:
        """Transform top-level await/async statements to asyncio.run() calls."""
        lines = code.splitlines()
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            is_top_level = line and not line[0].isspace()

            if is_top_level and stripped:
                # var = await expr()
                if " = await " in stripped and not stripped.startswith("async "):
                    stmt, i = self._collect_multiline(lines, i)
                    var, await_expr = stmt[0].split(" = await ", 1)
                    result.extend(self._wrap_async(await_expr, stmt[1:], var.strip()))
                    continue

                # await expr()
                if stripped.startswith("await "):
                    stmt, i = self._collect_multiline(lines, i)
                    result.extend(self._wrap_async(stmt[0][6:], stmt[1:]))
                    continue

                # async for ...
                if stripped.startswith("async for "):
                    block, i = self._collect_block(lines, i)
                    result.extend(self._wrap_async_block(block))
                    continue

            result.append(line)
            i += 1

        return "\n".join(result)

    def _wrap_async(self, first_expr: str, cont_lines: list[str], var_name: str | None = None) -> list[str]:
        """Wrap await expression in async helper function."""
        name = f"_async_helper_{self._helper_counter}"
        self._helper_counter += 1

        lines = [f"async def {name}():", f"    return await {first_expr}"]
        lines.extend(f"    {line}" for line in cont_lines)
        lines.append(f"{var_name} = asyncio.run({name}())" if var_name else f"asyncio.run({name}())")
        return lines

    def _wrap_async_block(self, block: list[str]) -> list[str]:
        """Wrap async for block in async function."""
        name = f"_async_for_{self._helper_counter}"
        self._helper_counter += 1

        lines = [f"async def {name}():"]
        lines.extend(f"    {line}" for line in block)
        lines.append(f"asyncio.run({name}())")
        return lines

    def _collect_multiline(self, lines: list[str], start: int) -> tuple[list[str], int]:
        """Collect multi-line statement by tracking bracket balance."""
        collected = [lines[start]]
        balance = self._bracket_balance(lines[start])
        i = start + 1

        while balance > 0 and i < len(lines):
            collected.append(lines[i])
            balance += self._bracket_balance(lines[i])
            i += 1

        return collected, i

    def _collect_block(self, lines: list[str], start: int) -> tuple[list[str], int]:
        """Collect indented block starting at given line."""
        block = [lines[start]]
        i = start + 1

        while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
            block.append(lines[i])
            i += 1

        return block, i

    def _bracket_balance(self, line: str) -> int:
        """Count net opening brackets, ignoring those inside strings."""
        balance = 0
        in_string = False
        string_char = None
        prev = None

        for char in line:
            if in_string:
                if char == string_char and prev != "\\":
                    in_string = False
            elif char in "\"'":
                in_string, string_char = True, char
            elif char in "([{":
                balance += 1
            elif char in ")]}":
                balance -= 1
            prev = char

        return balance

    # --- Script Generation ---

    def generate_script(self, skip_cells: list[int] | None = None) -> str:
        """Generate a complete executable Python script from the notebook."""
        header = SCRIPT_HEADER.format(name=self.notebook_path.name, working_dir=self.working_dir)

        cells = [
            f"\n# {'═' * 3} Cell {cell.number} {'═' * 3}\n{self.transform_cell(cell)}"
            for cell in self.extract_code_cells(skip_cells)
        ]

        return header + "\n".join(cells)

    def save_script(self, output_path: Path, skip_cells: list[int] | None = None) -> Path:
        """Generate and save the executable script."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.generate_script(skip_cells))
        return output_path
