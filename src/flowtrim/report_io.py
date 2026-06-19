from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark import (
    SCHEMA,
    BenchmarkCase,
    BenchmarkReport,
    BenchmarkStatus,
    MethodMeasurement,
    MetricFamily,
    PreservationSummary,
    RuntimeChanges,
    ToolInfo,
)
from .models import Lane


def report_from_json(source: str | Path | dict[str, Any]) -> BenchmarkReport:
    data = _load_json_source(source)
    if data.get("schema") != SCHEMA:
        raise ValueError("schema mismatch")

    return BenchmarkReport(
        schema=data["schema"],
        profile=str(data["profile"]),
        runtime_changes=_runtime_changes(data.get("runtime_changes", {})),
        tools=[_tool(tool) for tool in data.get("tools", [])],
        cases=[_case(case) for case in data.get("cases", [])],
        metric_totals=data.get("metric_totals", {}),
        vault_verdict=str(data.get("vault_verdict", "")),
        upgrade_backlog=[str(item) for item in data.get("upgrade_backlog", [])],
    )


def report_from_json_file(path: str | Path) -> BenchmarkReport:
    return report_from_json(Path(path).read_text(encoding="utf-8"))


def _load_json_source(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    else:
        text = source
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid report json") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid report json")
    return data


def _runtime_changes(data: dict[str, Any]) -> RuntimeChanges:
    return RuntimeChanges(
        installs=bool(data.get("installs", False)),
        hooks=bool(data.get("hooks", False)),
        proxy=bool(data.get("proxy", False)),
        mcp=bool(data.get("mcp", False)),
        config_writes=bool(data.get("config_writes", False)),
        telemetry=bool(data.get("telemetry", False)),
        stores_raw_output=bool(data.get("stores_raw_output", False)),
        unapproved_filesystem_writes=bool(data.get("unapproved_filesystem_writes", False)),
    )


def _tool(data: dict[str, Any]) -> ToolInfo:
    return ToolInfo(
        name=str(data.get("name", "")),
        available=bool(data.get("available", False)),
        version=data.get("version"),
        reason=data.get("reason"),
    )


def _case(data: dict[str, Any]) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=str(data.get("case_id", "")),
        lane=Lane(data["lane"]),
        fixture=str(data.get("fixture", "")),
        metric_family=MetricFamily(data["metric_family"]),
        methods=[_method(method) for method in data.get("methods", [])],
        preservation=_preservation(data.get("preservation", {})),
        runtime_changes=_runtime_changes(data.get("runtime_changes", {})),
        selected_method=data.get("selected_method"),
        winner=data.get("winner"),
        counts_as_claim=bool(data.get("counts_as_claim", False)),
        decision_reason=data.get("decision_reason"),
    )


def _method(data: dict[str, Any]) -> MethodMeasurement:
    return MethodMeasurement(
        method=str(data.get("method", "")),
        status=BenchmarkStatus(data["status"]),
        tokens=int(data.get("tokens", 0)),
        wall_time_ms=int(data.get("wall_time_ms", 0)),
        timeout=bool(data.get("timeout", False)),
        repeat_count=int(data.get("repeat_count", 0)),
        guard_passed=bool(data.get("guard_passed", False)),
        reason=data.get("reason"),
        payload=data.get("payload"),
    )


def _preservation(data: dict[str, Any]) -> PreservationSummary:
    return PreservationSummary(
        passed=bool(data.get("passed", False)),
        missing_items=[str(item) for item in data.get("missing_items", [])],
    )
