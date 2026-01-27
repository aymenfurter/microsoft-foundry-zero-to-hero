"""
Report generation for test results.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .models import TestConfig, TestSuiteResult, TestStatus


class ReportGenerator:
    """Generates test reports in various formats."""

    def __init__(self, config: TestConfig):
        self.config = config
        self.output_dir = config.settings.workspace_root / config.settings.output_dir

    def generate_junit(self, result: TestSuiteResult) -> Path:
        """Generate JUnit XML report for CI integration."""
        testsuite = ET.Element("testsuite", {
            "name": "foundry-workshop",
            "tests": str(len(result.notebooks)),
            "failures": str(result.failed),
            "time": f"{result.duration_seconds:.2f}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        for nb in result.notebooks:
            testcase = ET.SubElement(testsuite, "testcase", {
                "name": nb.name,
                "classname": "notebooks",
                "time": f"{nb.duration_seconds:.2f}",
            })

            if nb.status == TestStatus.FAILED:
                failure = ET.SubElement(testcase, "failure", {
                    "message": "Notebook execution failed",
                })
                failure.text = nb.error_message or "Unknown error"
            elif nb.status == TestStatus.SKIPPED:
                ET.SubElement(testcase, "skipped")

        tree = ET.ElementTree(testsuite)
        output_path = self.output_dir / "junit-report.xml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="unicode", xml_declaration=True)
        return output_path

    def generate_markdown(self, result: TestSuiteResult) -> Path:
        """Generate Markdown report."""
        lines = [
            "# Foundry Workshop Test Report",
            "",
            f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Duration:** {result.duration_seconds:.1f}s",
            f"**Status:** {'PASSED' if result.status == TestStatus.PASSED else 'FAILED'}",
            "",
            "## Summary",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total  | {len(result.notebooks)} |",
            f"| Passed | {result.passed} |",
            f"| Failed | {result.failed} |",
            f"| Skipped | {result.skipped} |",
            "",
            "## Results",
            "",
            "| Notebook | Status | Duration |",
            "|----------|--------|----------|",
        ]

        for nb in result.notebooks:
            status_icon = "PASS" if nb.status == TestStatus.PASSED else "FAIL" if nb.status == TestStatus.FAILED else "SKIP"
            lines.append(f"| {nb.name} | {status_icon} | {nb.duration_seconds:.1f}s |")

        # Add failure details
        failures = [nb for nb in result.notebooks if nb.status == TestStatus.FAILED]
        if failures:
            lines.extend(["", "## Failure Details", ""])
            for nb in failures:
                lines.append(f"### {nb.name}")
                lines.append("")
                lines.append("```")
                lines.append(nb.error_message or "No error message")
                lines.append("```")
                lines.append("")

        output_path = self.output_dir / "test-report.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines))
        return output_path

    def generate_html(self, result: TestSuiteResult) -> Path:
        """Generate HTML report with styling."""
        status_class = "passed" if result.status == TestStatus.PASSED else "failed"
        
        rows = []
        for nb in result.notebooks:
            status_icon = "&#x2713;" if nb.status == TestStatus.PASSED else "&#x2717;"
            row_class = "pass" if nb.status == TestStatus.PASSED else "fail"
            rows.append(f"""
                <tr class="{row_class}">
                    <td>{nb.name}</td>
                    <td class="status">{status_icon}</td>
                    <td>{nb.duration_seconds:.1f}s</td>
                </tr>
            """)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Foundry Workshop Test Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #0d1117;
            color: #c9d1d9;
        }}
        h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin: 2rem 0;
        }}
        .stat {{
            background: #161b22;
            padding: 1rem;
            border-radius: 6px;
            text-align: center;
            border: 1px solid #30363d;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-label {{ color: #8b949e; font-size: 0.875rem; }}
        .stat.passed .stat-value {{ color: #3fb950; }}
        .stat.failed .stat-value {{ color: #f85149; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }}
        th {{ background: #161b22; color: #8b949e; font-weight: 600; }}
        tr.pass td {{ background: rgba(63, 185, 80, 0.1); }}
        tr.fail td {{ background: rgba(248, 81, 73, 0.1); }}
        .status {{ text-align: center; font-size: 1.25rem; }}
        tr.pass .status {{ color: #3fb950; }}
        tr.fail .status {{ color: #f85149; }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 2rem;
            font-weight: 600;
        }}
        .badge.passed {{ background: #238636; color: white; }}
        .badge.failed {{ background: #da3633; color: white; }}
        .meta {{ color: #8b949e; margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <h1>Foundry Workshop Test Report</h1>
    
    <p class="meta">
        Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC |
        Duration: {result.duration_seconds:.1f}s |
        <span class="badge {status_class}">{result.status.value.upper()}</span>
    </p>

    <div class="summary">
        <div class="stat">
            <div class="stat-value">{len(result.notebooks)}</div>
            <div class="stat-label">Total</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{result.passed}</div>
            <div class="stat-label">Passed</div>
        </div>
        <div class="stat failed">
            <div class="stat-value">{result.failed}</div>
            <div class="stat-label">Failed</div>
        </div>
        <div class="stat">
            <div class="stat-value">{result.skipped}</div>
            <div class="stat-label">Skipped</div>
        </div>
    </div>

    <h2>Results</h2>
    <table>
        <thead>
            <tr>
                <th>Notebook</th>
                <th style="width: 80px; text-align: center;">Status</th>
                <th style="width: 100px;">Duration</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</body>
</html>"""

        output_path = self.output_dir / "test-report.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        return output_path
