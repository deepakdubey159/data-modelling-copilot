"""Estimation result writer.

Writes effort estimation to JSON, Markdown, and HTML formats.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from migration.estimation.models import EstimationPackage

logger = logging.getLogger(__name__)


class EstimationWriter:
    """Writes estimation results to disk."""

    def write(self, package: EstimationPackage, run_directory: Path) -> tuple[Path, Path, Path]:
        """Write estimation in all formats. Returns (json, markdown, html)."""
        return (
            self.write_json(package, run_directory),
            self.write_markdown(package, run_directory),
            self.write_html(package, run_directory),
        )

    def write_json(self, package: EstimationPackage, run_directory: Path) -> Path:
        """Write estimation as JSON."""
        output_file = run_directory / "estimation.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(package.model_dump(mode="json"), fp, indent=4, default=str)
        return output_file

    def write_markdown(self, package: EstimationPackage, run_directory: Path) -> Path:
        """Write estimation as Markdown."""
        output_file = run_directory / "estimation.md"
        result = package.estimation_result

        lines = [
            "# Migration Effort Estimation",
            "",
            "## Executive Summary",
            "",
            f"**Complexity Level:** {result.complexity_level.value}",
            f"**Total Effort:** {result.total_effort_days:.1f} person-days "
            f"({result.total_effort_weeks:.1f} weeks, {result.total_effort_months:.1f} months)",
            f"**Confidence:** {result.confidence_level}",
            "",
            f"**Source:** {result.source_type}",
            f"**Target:** {result.target_type}",
            "",
            "## Effort Breakdown",
            "",
            "| Component | Effort (Days) |",
            "|-----------|---------------|",
        ]

        for component in result.effort_components:
            lines.append(
                f"| {component.name} | {component.effort_days:.1f} |"
            )

        lines.extend([
            "",
            f"| **Total** | **{result.total_effort_days:.1f}** |",
            "",
            "## Complexity Factors",
            "",
            "| Factor | Value |",
            "|--------|-------|",
            f"| Tables | {result.complexity_factors.table_count} |",
            f"| Columns | {result.complexity_factors.total_columns} |",
            f"| Primary Keys | {result.complexity_factors.primary_key_relationships} |",
            f"| Foreign Keys | {result.complexity_factors.foreign_key_relationships} |",
            f"| Complex Relationships | {result.complexity_factors.complex_relationships} |",
            f"| Unique Constraints | {result.complexity_factors.unique_constraints} |",
            f"| Check Constraints | {result.complexity_factors.check_constraints} |",
            f"| Large Tables | {result.complexity_factors.large_tables} |",
            f"| Datatype Conversions | {result.complexity_factors.datatype_conversions} |",
        ])

        # Add DB2-specific factors if present
        if result.source_type.lower() == "db2":
            lines.extend([
                "",
                "### DB2-Specific Complexity Factors",
                "",
                "| Factor | Value |",
                "|--------|-------|",
                f"| Views | {result.complexity_factors.views_count} |",
                f"| Stored Procedures | {result.complexity_factors.procedures_count} |",
                f"| Triggers | {result.complexity_factors.triggers_count} |",
                f"| Legacy DB2 Datatypes | {result.complexity_factors.db2_legacy_datatypes} |",
                f"| LOB Columns (CLOB/BLOB/XML) | {result.complexity_factors.db2_lob_columns} |",
                f"| GRAPHIC/VARGRAPHIC Columns | {result.complexity_factors.db2_graphic_columns} |",
                f"| DECIMAL/DECFLOAT Columns | {result.complexity_factors.db2_decimal_columns} |",
                f"| XML Columns | {result.complexity_factors.db2_xml_columns} |",
                f"| Indexes | {result.complexity_factors.db2_indexes} |",
            ])

        lines.extend([
            "",
            "## Effort Component Details",
            "",
        ])

        for component in result.effort_components:
            lines.extend([
                f"### {component.name}",
                "",
                f"{component.description}",
                "",
                f"**Estimated Effort:** {component.effort_days:.1f} person-days",
                "",
            ])

        lines.extend([
            "## Assumptions",
            "",
        ])

        for assumption in result.assumptions:
            lines.append(f"- {assumption}")

        lines.extend([
            "",
            "## Identified Risks",
            "",
        ])

        for risk in result.risks:
            lines.append(f"- {risk}")

        lines.extend([
            "",
            "## Recommendations",
            "",
        ])

        for rec in result.recommendations:
            lines.append(f"- {rec}")

        lines.extend([
            "",
            "---",
            "",
            "**Note:** This estimation is based on schema complexity analysis. Actual effort",
            "may vary based on data quality, business logic complexity, and team experience.",
        ])

        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write("\n".join(lines))

        return output_file

    def write_html(self, package: EstimationPackage, run_directory: Path) -> Path:
        """Write estimation as HTML."""
        output_file = run_directory / "estimation.html"
        result = package.estimation_result

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migration Effort Estimation</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #7f8c8d;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .complexity-{result.complexity_level.value.lower()} {{
            background: {"#fee" if "HIGH" in result.complexity_level.value else "#efe"};
            border-left-color: {"#f55" if "HIGH" in result.complexity_level.value else "#5f5"};
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #34495e;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .effort-bar {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .bar {{
            flex: 1;
            height: 20px;
            background: #3498db;
            border-radius: 3px;
            max-width: 300px;
        }}
        .risk {{
            background: #fee;
            border-left: 4px solid #f55;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .recommendation {{
            background: #efe;
            border-left: 4px solid #5f5;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .assumption {{
            padding: 10px;
            margin: 5px 0;
            background: #f0f0f0;
            border-radius: 3px;
        }}
        @media (prefers-color-scheme: dark) {{
            body {{ background: #1e1e1e; color: #e0e0e0; }}
            .container {{ background: #2d2d2d; }}
            h1, h2 {{ color: #e0e0e0; }}
            .summary-card {{ background: #404040; color: #b0b0b0; }}
            .summary-card .value {{ color: #e0e0e0; }}
            th {{ background: #1a1a1a; }}
            tr:hover {{ background: #3a3a3a; }}
            .assumption {{ background: #3a3a3a; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Migration Effort Estimation</h1>

        <div class="summary">
            <div class="summary-card complexity-{result.complexity_level.value.lower()}">
                <h3>Complexity Level</h3>
                <div class="value">{result.complexity_level.value}</div>
            </div>
            <div class="summary-card">
                <h3>Total Effort</h3>
                <div class="value">{result.total_effort_days:.0f} days</div>
                <small>({result.total_effort_weeks:.1f} weeks, {result.total_effort_months:.1f} months)</small>
            </div>
            <div class="summary-card">
                <h3>Source → Target</h3>
                <div class="value">{result.source_type} → {result.target_type}</div>
            </div>
            <div class="summary-card">
                <h3>Confidence Level</h3>
                <div class="value">{result.confidence_level}</div>
            </div>
        </div>

        <h2>Effort Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Component</th>
                    <th>Effort (Days)</th>
                    <th>Visualization</th>
                </tr>
            </thead>
            <tbody>
"""

        max_effort = max(c.effort_days for c in result.effort_components) if result.effort_components else 1
        for component in result.effort_components:
            bar_width = (component.effort_days / max_effort) * 300
            html += f"""
                <tr>
                    <td>{component.name}</td>
                    <td>{component.effort_days:.1f}</td>
                    <td>
                        <div class="effort-bar">
                            <div class="bar" style="width: {bar_width}px;"></div>
                        </div>
                    </td>
                </tr>
"""

        html += f"""
                <tr style="font-weight: bold; background: #ecf0f1;">
                    <td>Total</td>
                    <td>{result.total_effort_days:.1f}</td>
                    <td></td>
                </tr>
            </tbody>
        </table>

        <h2>Complexity Factors</h2>
        <table>
            <thead>
                <tr>
                    <th>Factor</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Tables</td>
                    <td>{result.complexity_factors.table_count}</td>
                </tr>
                <tr>
                    <td>Columns</td>
                    <td>{result.complexity_factors.total_columns}</td>
                </tr>
                <tr>
                    <td>Primary Keys</td>
                    <td>{result.complexity_factors.primary_key_relationships}</td>
                </tr>
                <tr>
                    <td>Foreign Keys</td>
                    <td>{result.complexity_factors.foreign_key_relationships}</td>
                </tr>
                <tr>
                    <td>Complex Relationships</td>
                    <td>{result.complexity_factors.complex_relationships}</td>
                </tr>
                <tr>
                    <td>Large Tables</td>
                    <td>{result.complexity_factors.large_tables}</td>
                </tr>
                <tr>
                    <td>Datatype Conversions</td>
                    <td>{result.complexity_factors.datatype_conversions}</td>
                </tr>
            </tbody>
        </table>
"""

        # Add DB2-specific complexity factors table
        if result.source_type.lower() == "db2":
            html += f"""
        <h2>DB2-Specific Complexity Factors</h2>
        <table>
            <thead>
                <tr>
                    <th>Factor</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Views</td>
                    <td>{result.complexity_factors.views_count}</td>
                </tr>
                <tr>
                    <td>Stored Procedures</td>
                    <td>{result.complexity_factors.procedures_count}</td>
                </tr>
                <tr>
                    <td>Triggers</td>
                    <td>{result.complexity_factors.triggers_count}</td>
                </tr>
                <tr>
                    <td>Legacy DB2 Datatypes</td>
                    <td>{result.complexity_factors.db2_legacy_datatypes}</td>
                </tr>
                <tr>
                    <td>LOB Columns (CLOB/BLOB/XML)</td>
                    <td>{result.complexity_factors.db2_lob_columns}</td>
                </tr>
                <tr>
                    <td>GRAPHIC/VARGRAPHIC Columns</td>
                    <td>{result.complexity_factors.db2_graphic_columns}</td>
                </tr>
                <tr>
                    <td>DECIMAL/DECFLOAT Columns</td>
                    <td>{result.complexity_factors.db2_decimal_columns}</td>
                </tr>
                <tr>
                    <td>XML Columns</td>
                    <td>{result.complexity_factors.db2_xml_columns}</td>
                </tr>
                <tr>
                    <td>Indexes</td>
                    <td>{result.complexity_factors.db2_indexes}</td>
                </tr>
            </tbody>
        </table>
"""

        html += """
        <h2>Risks</h2>
"""

        for risk in result.risks:
            html += f'        <div class="risk">⚠️ {risk}</div>\n'

        html += """
        <h2>Recommendations</h2>
"""

        for rec in result.recommendations:
            html += f'        <div class="recommendation">✓ {rec}</div>\n'

        html += """
        <h2>Assumptions</h2>
"""

        for assumption in result.assumptions:
            html += f'        <div class="assumption">• {assumption}</div>\n'

        html += """
    </div>
</body>
</html>
"""

        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(html)

        return output_file
