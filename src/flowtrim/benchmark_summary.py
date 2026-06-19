from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .benchmark import BenchmarkReport
from .privacy import scan_text
from .report_io import report_from_json_file


SCHEMA = "flowtrim-benchmark-summary/v1"


@dataclass(frozen=True)
class SummaryRow:
    profile: str
    cases: int
    token_wins: int
    tokens_saved: int
    raw_refusals: int
    code_lens_wins: int
    claim_boundary: str


def load_summary_reports(paths: list[str | Path]) -> list[BenchmarkReport]:
    if not paths:
        raise ValueError("benchmark-summary requires at least one --report")
    reports: list[BenchmarkReport] = []
    for path in paths:
        try:
            reports.append(report_from_json_file(path))
        except OSError as exc:
            raise ValueError("report unreadable") from exc
    return reports


def summarize_reports(reports: list[BenchmarkReport]) -> dict[str, Any]:
    rows = [_row(report) for report in reports]
    payload = {
        "schema": SCHEMA,
        "profile_count": len(rows),
        "totals": {
            "cases": sum(row.cases for row in rows),
            "token_wins": sum(row.token_wins for row in rows),
            "tokens_saved": sum(row.tokens_saved for row in rows),
            "raw_refusals": sum(row.raw_refusals for row in rows),
            "code_lens_wins": sum(row.code_lens_wins for row in rows),
        },
        "rows": [row.__dict__ for row in rows],
        "claim": "No global benchmark claim; evidence is lane-specific.",
    }
    _assert_public_safe(json.dumps(payload, sort_keys=True))
    return payload


def summary_to_json(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True)
    _assert_public_safe(text)
    return text


def summary_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FlowTrim Public Alpha Benchmark",
        "",
        "Aggregate-only scoreboard generated from sanitized FlowTrim reports.",
        "It supports lane-specific evidence only, not a global benchmark claim.",
        "",
        "| Profile | Cases | Token wins | Tokens saved | Raw refusals | Code-lens wins | Claim boundary |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {profile} | {cases} | {token_wins} | {tokens_saved} | {raw_refusals} | {code_lens_wins} | {claim_boundary} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Reading The Numbers",
            "",
            "- Token wins count only when a smaller method preserves required facts and stays within the wall-time budget.",
            "- Raw refusals are good outcomes for exact evidence such as quotes, stack traces, and line-level diffs.",
            "- Code-lens wins are complexity-reduction evidence, not direct token-saving claims.",
            "- Headroom skipped or unavailable is neutral, not a loss.",
            "",
            "No private Work repo names, paths, commit messages, source lines, or raw diffs are included.",
        ]
    )
    text = "\n".join(lines)
    _assert_public_safe(text)
    return text


def summary_to_svg(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    width = 980
    height = 170 + 54 * len(rows)
    max_tokens = max([row["tokens_saved"] for row in rows] + [1])
    max_code = max([row["code_lens_wins"] for row in rows] + [1])
    chart_x = 250
    chart_w = 300
    code_x = 650
    code_w = 210
    colors = {
        "token": "#0f766e",
        "code": "#7c3aed",
        "text": "#172554",
        "muted": "#475569",
        "grid": "#e2e8f0",
        "bg": "#ffffff",
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="FlowTrim public alpha benchmark" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{colors["bg"]}"/>',
        f'<text x="32" y="42" font-family="Inter, Arial, sans-serif" font-size="26" font-weight="700" fill="{colors["text"]}">FlowTrim public alpha benchmark</text>',
        f'<text x="32" y="70" font-family="Inter, Arial, sans-serif" font-size="14" fill="{colors["muted"]}">Lane-specific wins from sanitized public-safe reports. No global benchmark claim.</text>',
        f'<text x="{chart_x}" y="110" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="700" fill="{colors["text"]}">estimated tokens saved</text>',
        f'<text x="{code_x}" y="110" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="700" fill="{colors["text"]}">code-lens wins</text>',
    ]

    for index, row in enumerate(rows):
        y = 145 + index * 54
        token_w = int((row["tokens_saved"] / max_tokens) * chart_w)
        code_width = int((row["code_lens_wins"] / max_code) * code_w)
        parts.extend(
            [
                f'<line x1="32" x2="948" y1="{y + 28}" y2="{y + 28}" stroke="{colors["grid"]}" stroke-width="1"/>',
                f'<text x="32" y="{y}" font-family="Inter, Arial, sans-serif" font-size="14" font-weight="700" fill="{colors["text"]}">{html.escape(row["profile"])}</text>',
                f'<text x="32" y="{y + 20}" font-family="Inter, Arial, sans-serif" font-size="12" fill="{colors["muted"]}">{row["cases"]} cases - {row["raw_refusals"]} raw refusals</text>',
                f'<rect x="{chart_x}" y="{y - 15}" width="{chart_w}" height="18" rx="4" fill="{colors["grid"]}"/>',
                f'<rect x="{chart_x}" y="{y - 15}" width="{max(token_w, 2)}" height="18" rx="4" fill="{colors["token"]}"/>',
                f'<text x="{chart_x + chart_w + 12}" y="{y}" font-family="Inter, Arial, sans-serif" font-size="13" fill="{colors["text"]}">{row["tokens_saved"]}</text>',
                f'<rect x="{code_x}" y="{y - 15}" width="{code_w}" height="18" rx="4" fill="{colors["grid"]}"/>',
                f'<rect x="{code_x}" y="{y - 15}" width="{max(code_width, 2)}" height="18" rx="4" fill="{colors["code"]}"/>',
                f'<text x="{code_x + code_w + 12}" y="{y}" font-family="Inter, Arial, sans-serif" font-size="13" fill="{colors["text"]}">{row["code_lens_wins"]}</text>',
            ]
        )

    parts.append("</svg>")
    text = "\n".join(parts)
    _assert_public_safe(text)
    return text


def write_summary_outputs(
    payload: dict[str, Any],
    *,
    markdown_out: str | Path | None,
    svg_out: str | Path | None,
) -> None:
    if markdown_out:
        path = Path(markdown_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary_to_markdown(payload) + "\n", encoding="utf-8")
    if svg_out:
        path = Path(svg_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary_to_svg(payload) + "\n", encoding="utf-8")


def _row(report: BenchmarkReport) -> SummaryRow:
    bearing_totals = report.metric_totals["token-bearing"]
    refusal = report.metric_totals["refusal-correctness"]
    code = report.metric_totals["code-lens"]
    return SummaryRow(
        profile=report.profile,
        cases=len(report.cases),
        token_wins=int(bearing_totals.get("wins", 0)),
        tokens_saved=int(bearing_totals.get("tokens_saved", 0)),
        raw_refusals=int(refusal.get("correct_refusals", 0)),
        code_lens_wins=int(code.get("wins", 0)),
        claim_boundary=_claim_boundary(report.profile),
    )


def _claim_boundary(profile: str) -> str:
    if profile == "public-open-source-readonly":
        return "Pinned public corpus only"
    if profile == "public-playground-readonly":
        return "Public-safe usability smoke"
    if profile == "synthetic-heavy":
        return "Public-safe fixture evidence"
    if profile.startswith("work-"):
        return "Private local evidence only"
    if profile == "aql-vault-readonly":
        return "Vault baseline check only"
    return "Lane-specific evidence only"


def _assert_public_safe(text: str) -> None:
    findings = scan_text(text)
    if findings:
        raise ValueError("benchmark summary privacy finding")
