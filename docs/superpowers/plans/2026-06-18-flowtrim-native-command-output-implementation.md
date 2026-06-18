# FlowTrim Native Command Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first FlowTrim-native command-output compactor and prove it can beat raw and RTK fixture replay safely on measured noisy command-output cases.

**Architecture:** Add a small scorecard module for explicit `native-win`, `baseline-win`, `raw-win`, `insufficient-evidence`, and `skipped-neutral` labels. Add a clean-room `native_command` module that turns noisy logs into structured packets and a sanitized snippet. Wire it into `synthetic-heavy` beside raw and RTK without changing non-command lanes.

**Tech Stack:** Python 3.11, `unittest`, existing FlowTrim benchmark dataclasses, no new runtime dependencies.

---

## Scope

Implement Phase 1 and Phase 2 from `docs/superpowers/specs/2026-06-18-flowtrim-final-native-core-design.md`.

In scope:

- Scorecard labels and lane-specific comparison summaries.
- Native command-output packetizer for public-safe test/build logs.
- Synthetic benchmark comparison of raw, RTK fixture replay, and FlowTrim native.
- Proof that native command-output wins noisy synthetic command cases only when preservation and token gates pass.
- Documentation update explaining that RTK remains an optional baseline/backend.

Out of scope:

- Native code-complexity lens.
- Native long-context packetizer.
- Public open-source corpus.
- Live RTK execution beyond existing safe fixture replay and availability/version capture.
- Any install, hook, proxy, MCP, telemetry, memory, or persistent config write.

## File Structure

- Create `src/flowtrim/scorecard.py`: score labels and comparison helpers.
- Create `src/flowtrim/native_command.py`: clean-room command-output packetizer and measurement adapter.
- Create `tests/test_scorecard.py`: scorecard unit tests.
- Create `tests/test_native_command.py`: packetizer unit tests.
- Modify `src/flowtrim/benchmark.py`: add safe payload keys, wire native command measurements into synthetic command cases, expose native-vs-baseline method selection in reports.
- Modify `tests/test_proof_matrix.py`: update noisy command expectations from `rtk` to `flowtrim-native-command`, while keeping RTK as measured baseline.
- Modify `tests/test_suite.py`: assert synthetic reports contain raw, RTK, and native command methods for noisy command cases.
- Modify `docs/benchmark-results.md`: add a short note that native command-output is the first active final-direction implementation once verification passes.
- Modify `README.md`: document `FlowTrim + RTK` as current safe mode and native command-output as the first challenger.

## Task 1: Scorecard Labels

**Files:**
- Create: `src/flowtrim/scorecard.py`
- Create: `tests/test_scorecard.py`

- [ ] **Step 1: Write the failing tests**

Add `tests/test_scorecard.py`:

```python
import unittest

from flowtrim.scorecard import DecisionLabel, ScorecardResult, compare_token_methods


class ScorecardTest(unittest.TestCase):
    def test_native_win_requires_primary_score_and_all_guards(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=40,
            baseline_tokens=55,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.NATIVE_WIN)
        self.assertEqual(result.primary_delta, 60)
        self.assertEqual(result.selected_method, "flowtrim-native-command")

    def test_baseline_win_when_baseline_is_safer_or_smaller(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=60,
            baseline_tokens=40,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.BASELINE_WIN)
        self.assertEqual(result.selected_method, "rtk")

    def test_raw_win_for_short_output_or_over_budget_candidates(self):
        short = compare_token_methods(
            raw_tokens=3,
            native_tokens=1,
            baseline_tokens=1,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )
        slow = compare_token_methods(
            raw_tokens=100,
            native_tokens=10,
            baseline_tokens=20,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=999,
            baseline_wall_time_ms=999,
            wall_time_budget_ms=250,
        )

        self.assertEqual(short.label, DecisionLabel.RAW_WIN)
        self.assertEqual(slow.label, DecisionLabel.RAW_WIN)

    def test_insufficient_evidence_when_smaller_candidate_fails_guard(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=10,
            baseline_tokens=20,
            native_guard_passed=False,
            baseline_guard_passed=False,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.selected_method)
        self.assertIsInstance(result, ScorecardResult)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_scorecard
```

Expected: fail with `ModuleNotFoundError: No module named 'flowtrim.scorecard'`.

- [ ] **Step 3: Implement the scorecard module**

Create `src/flowtrim/scorecard.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionLabel(StrEnum):
    NATIVE_WIN = "native-win"
    BASELINE_WIN = "baseline-win"
    RAW_WIN = "raw-win"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    SKIPPED_NEUTRAL = "skipped-neutral"


@dataclass(frozen=True)
class ScorecardResult:
    label: DecisionLabel
    selected_method: str | None
    primary_delta: int
    reason: str


def compare_token_methods(
    *,
    raw_tokens: int,
    native_tokens: int | None,
    baseline_tokens: int | None,
    native_guard_passed: bool,
    baseline_guard_passed: bool,
    native_wall_time_ms: int,
    baseline_wall_time_ms: int,
    wall_time_budget_ms: int,
    raw_short_token_limit: int = 8,
) -> ScorecardResult:
    if raw_tokens <= raw_short_token_limit:
        return ScorecardResult(DecisionLabel.RAW_WIN, "raw", 0, "raw-short-output")

    native_can_win = (
        native_tokens is not None
        and native_guard_passed
        and native_wall_time_ms <= wall_time_budget_ms
        and native_tokens < raw_tokens
    )
    baseline_can_win = (
        baseline_tokens is not None
        and baseline_guard_passed
        and baseline_wall_time_ms <= wall_time_budget_ms
        and baseline_tokens < raw_tokens
    )

    candidates: list[tuple[int, int, str, DecisionLabel]] = []
    if native_can_win:
        candidates.append(
            (native_tokens, native_wall_time_ms, "flowtrim-native-command", DecisionLabel.NATIVE_WIN)
        )
    if baseline_can_win:
        candidates.append((baseline_tokens, baseline_wall_time_ms, "rtk", DecisionLabel.BASELINE_WIN))

    if candidates:
        tokens, _wall_time, method, label = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        return ScorecardResult(label, method, raw_tokens - tokens, "lower-token-safe")

    smaller_failed_guard = (
        (native_tokens is not None and native_tokens < raw_tokens and not native_guard_passed)
        or (baseline_tokens is not None and baseline_tokens < raw_tokens and not baseline_guard_passed)
    )
    if smaller_failed_guard:
        return ScorecardResult(
            DecisionLabel.INSUFFICIENT_EVIDENCE,
            None,
            0,
            "guard-failed",
        )

    return ScorecardResult(DecisionLabel.RAW_WIN, "raw", 0, "raw-best")
```

- [ ] **Step 4: Run the scorecard tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_scorecard
```

Expected: pass.

- [ ] **Step 5: Run existing benchmark tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_benchmark tests.test_suite
```

Expected: pass.

## Task 2: Native Command Packetizer

**Files:**
- Create: `src/flowtrim/native_command.py`
- Create: `tests/test_native_command.py`

- [ ] **Step 1: Write the failing tests**

Add `tests/test_native_command.py`:

```python
import unittest

from flowtrim.native_command import FlowTrimNativeCommand, compact_command_output
from flowtrim.models import Lane


class NativeCommandTest(unittest.TestCase):
    def test_compacts_noisy_passing_build_and_preserves_required_facts(self):
        text = "\n".join(
            [
                "BUILD START demo-web",
                "src/example.py::test_user_flow PASSED",
                "src/example.py::test_billing_summary PASSED",
                "WARN keep: src/example.py uses FEATURE_FLAG_DEMO",
                "INFO noise: bundler chunk 001 completed",
                "INFO noise: bundler chunk 002 completed",
                "SUMMARY keep: 2 passed, 0 failed, artifact demo-build",
            ]
        )

        measurement = FlowTrimNativeCommand().measure(
            text,
            Lane.COMMAND_OUTPUT,
            must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
        )

        self.assertEqual(measurement.method, "flowtrim-native-command")
        self.assertTrue(measurement.guard_passed)
        self.assertLess(measurement.tokens, 18)
        self.assertEqual(measurement.payload["status"], "pass")
        self.assertIn("src/example.py", measurement.payload["primary_files"])
        self.assertIn("FEATURE_FLAG_DEMO", measurement.payload["must_keep"])
        self.assertIn("2 passed", measurement.payload["sanitized_snippet"])
        self.assertNotIn("raw_output", measurement.payload)

    def test_compacts_failing_build_and_preserves_error_and_failing_test(self):
        text = "\n".join(
            [
                "BUILD START demo-worker",
                "src/worker.py::test_retry_policy FAILED",
                "ERROR keep: RetryBudgetExceeded",
                "TRACE keep: src/worker.py:42 handle_retry",
                "INFO noise: dependency cache warmed 001",
                "SUMMARY keep: 1 failed, 18 passed, failing test src/worker.py::test_retry_policy",
            ]
        )

        packet = compact_command_output(
            text,
            must_preserve=(
                "src/worker.py",
                "RetryBudgetExceeded",
                "src/worker.py::test_retry_policy",
            ),
        )

        self.assertTrue(packet.guard_passed)
        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn("src/worker.py", packet.payload["primary_files"])
        self.assertIn("src/worker.py::test_retry_policy", packet.payload["failing_tests"])
        self.assertIn("RetryBudgetExceeded", packet.payload["error_labels"])

    def test_missing_required_fact_fails_guard(self):
        packet = compact_command_output(
            "ERROR keep: RetryBudgetExceeded",
            must_preserve=("src/worker.py", "RetryBudgetExceeded"),
        )

        self.assertFalse(packet.guard_passed)
        self.assertIn("missing required items", packet.reason)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_native_command
```

Expected: fail with `ModuleNotFoundError: No module named 'flowtrim.native_command'`.

- [ ] **Step 3: Implement native command module**

Create `src/flowtrim/native_command.py` with a clean-room parser using only
FlowTrim fixtures and tests:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .adapters import hash_text, median_measure
from .benchmark import BenchmarkStatus, MethodMeasurement
from .metrics import estimate_tokens
from .models import Lane


METHOD = "flowtrim-native-command"
PATH_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.:-]+\b")
TEST_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+::[A-Za-z0-9_:-]+\b")
ERROR_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception|Exceeded|Failure|Failed)\b")
SUMMARY_RE = re.compile(r"\b\d+\s+(?:passed|failed|errors?)\b", re.IGNORECASE)
NOISE_MARKERS = ("INFO noise:", "chunk", "cache warmed", "completed")


@dataclass(frozen=True)
class NativeCommandPacket:
    text: str
    payload: dict[str, Any]
    guard_passed: bool
    reason: str | None


class FlowTrimNativeCommand:
    def measure(
        self,
        text: str,
        lane: Lane,
        *,
        must_preserve: tuple[str, ...] = (),
        repeat_count: int = 3,
        timeout_ms: int = 250,
    ) -> MethodMeasurement:
        timing = median_measure(
            lambda: compact_command_output(text, must_preserve=must_preserve),
            repeat_count,
            timeout_ms,
        )
        packet: NativeCommandPacket = timing.value
        return MethodMeasurement(
            method=METHOD,
            status=BenchmarkStatus.TIMEOUT if timing.timeout else BenchmarkStatus.OK,
            tokens=estimate_tokens(packet.text),
            wall_time_ms=timing.wall_time_ms,
            timeout=timing.timeout,
            repeat_count=timing.repeat_count,
            guard_passed=packet.guard_passed and not timing.timeout,
            reason=packet.reason if not timing.timeout else "timeout",
            payload=packet.payload,
        )


def compact_command_output(
    text: str,
    *,
    must_preserve: tuple[str, ...] = (),
) -> NativeCommandPacket:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    primary_files = _unique(PATH_RE.findall(text))
    failing_tests = _unique(TEST_RE.findall(text))
    error_labels = _unique(ERROR_RE.findall(text))
    summary_facts = _unique(SUMMARY_RE.findall(text))
    status = _status(text)
    omitted = _omitted_noise_classes(lines)

    facts = [
        status,
        *primary_files[:2],
        *failing_tests[:2],
        *error_labels[:2],
        *summary_facts[:2],
        *must_preserve,
    ]
    snippet = " ".join(_unique([fact for fact in facts if fact and fact != "unknown"]))
    missing = [item for item in must_preserve if item and item not in snippet]
    payload = {
        "content_hash": hash_text(text),
        "status": status,
        "primary_files": primary_files[:5],
        "failing_tests": failing_tests[:5],
        "error_labels": error_labels[:5],
        "summary_lines": summary_facts[:5],
        "omitted_noise_classes": omitted,
        "must_keep": list(must_preserve),
        "sanitized_snippet": snippet,
    }
    return NativeCommandPacket(
        text=snippet,
        payload=payload,
        guard_passed=not missing,
        reason=None if not missing else "missing required items: " + ", ".join(missing),
    )


def _status(text: str) -> str:
    lowered = text.lower()
    if "failed" in lowered or "error keep:" in lowered:
        return "fail"
    if "passed" in lowered:
        return "pass"
    if "warn" in lowered:
        return "warning"
    return "unknown"


def _omitted_noise_classes(lines: list[str]) -> list[str]:
    classes = []
    if any(any(marker in line for marker in NOISE_MARKERS) for line in lines):
        classes.append("progress-noise")
    if len(lines) != len(set(lines)):
        classes.append("duplicate-lines")
    return classes


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
```

- [ ] **Step 4: Run native command tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_native_command
```

Expected: pass.

## Task 3: Wire Native Command Into Synthetic Benchmark

**Files:**
- Modify: `src/flowtrim/benchmark.py`
- Modify: `tests/test_suite.py`
- Modify: `tests/test_proof_matrix.py`

- [ ] **Step 1: Write failing benchmark tests**

In `tests/test_suite.py`, add a test that noisy command cases include raw, RTK,
and native methods, and that native has a structured packet:

```python
    def test_synthetic_noisy_command_cases_compare_native_against_rtk(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        noisy_cases = [
            case
            for case in report.cases
            if case.case_id in {
                "command-output/noisy-build-pass",
                "command-output/noisy-build-fail",
            }
        ]

        self.assertEqual(len(noisy_cases), 2)
        for case in noisy_cases:
            methods = {method.method: method for method in case.methods}
            self.assertIn("raw", methods)
            self.assertIn("rtk", methods)
            self.assertIn("flowtrim-native-command", methods)
            self.assertEqual(case.selected_method, "flowtrim-native-command")
            self.assertLess(methods["flowtrim-native-command"].tokens, methods["rtk"].tokens)
            self.assertTrue(methods["flowtrim-native-command"].guard_passed)
            self.assertIn("status", methods["flowtrim-native-command"].payload)
            self.assertIn("primary_files", methods["flowtrim-native-command"].payload)
```

In `tests/test_proof_matrix.py`, update `SYNTHETIC_EXPECTATIONS` for the two
noisy command cases:

```python
    "command-output/noisy-build-pass": (
        "flowtrim-native-command",
        "flowtrim-native-command",
        "lower-token-safe",
        True,
    ),
    "command-output/noisy-build-fail": (
        "flowtrim-native-command",
        "flowtrim-native-command",
        "lower-token-safe",
        True,
    ),
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_suite tests.test_proof_matrix
```

Expected: fail because benchmark still selects `rtk`.

- [ ] **Step 3: Add safe payload keys**

In `src/flowtrim/benchmark.py`, add these keys to `SAFE_PAYLOAD_KEYS`:

```python
        "error_labels",
        "failing_tests",
        "must_keep",
        "omitted_noise_classes",
        "primary_files",
        "status",
        "summary_lines",
```

- [ ] **Step 4: Add native command candidate helper**

In `src/flowtrim/benchmark.py`, add:

```python
def _native_command_candidate(
    input_text: str,
    *,
    must_preserve: tuple[str, ...],
) -> MethodMeasurement:
    from .native_command import FlowTrimNativeCommand

    return FlowTrimNativeCommand().measure(
        input_text,
        Lane.COMMAND_OUTPUT,
        must_preserve=must_preserve,
    )
```

- [ ] **Step 5: Wire noisy command cases**

Modify the two noisy command cases in `build_synthetic_heavy_suite()` so each
candidate list includes RTK and native:

```python
                _native_command_candidate(
                    noisy_pass,
                    must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
                ),
```

and:

```python
                _native_command_candidate(
                    noisy_fail,
                    must_preserve=(
                        "src/worker.py",
                        "RetryBudgetExceeded",
                        "src/worker.py::test_retry_policy",
                    ),
                ),
```

Keep the existing RTK fixture candidates so reports still compare against RTK.

- [ ] **Step 6: Run benchmark tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_suite tests.test_proof_matrix
```

Expected: pass.

## Task 4: Report And Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `docs/benchmark-results.md`

- [ ] **Step 1: Write documentation check**

Run this search before editing:

```bash
rg -n "FlowTrim \\+ RTK|native command|optional baseline|command-output" README.md docs/benchmark-results.md
```

Expected: existing docs mention command-output and optional tools, but not the
new native command challenger.

- [ ] **Step 2: Update README**

Add a short paragraph under `Benchmark Lab`:

```markdown
FlowTrim's first native challenger is `flowtrim-native-command`, a clean-room
command-output packetizer. RTK remains an optional baseline/backend: FlowTrim may
select RTK when it wins safely, but native command output can become selected
when it preserves required facts and beats both raw and RTK in the measured case.
```

- [ ] **Step 3: Update benchmark results doc**

Add a note near the synthetic-heavy section:

```markdown
Native command-output comparison is the first implementation stage of the final
direction. The noisy command fixtures compare raw, RTK fixture replay, and
`flowtrim-native-command`; wins count only when required facts survive and the
native packet is smaller within budget.
```

- [ ] **Step 4: Run documentation privacy scan**

Run:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from flowtrim.privacy import scan_text
bad = []
for rel in ["README.md", "docs/benchmark-results.md"]:
    findings = scan_text(Path(rel).read_text(errors="ignore"))
    if findings:
        bad.append((rel, findings))
print(bad)
raise SystemExit(1 if bad else 0)
PY
```

Expected: `[]`.

## Task 5: Full Verification And Benchmark Comparison

**Files:**
- No new files.

- [ ] **Step 1: Run full unit suite**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Run synthetic benchmark and inspect selected methods**

Run:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json > /tmp/flowtrim-native-synthetic.json
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("/tmp/flowtrim-native-synthetic.json").read_text())
for case in d["cases"]:
    if case["case_id"] in ("command-output/noisy-build-pass", "command-output/noisy-build-fail"):
        methods = {m["method"]: m for m in case["methods"]}
        print(case["case_id"], case["selected_method"], methods["raw"]["tokens"], methods["rtk"]["tokens"], methods["flowtrim-native-command"]["tokens"])
print(d["metric_totals"]["token-bearing"])
PY
```

Expected:

- both noisy command cases select `flowtrim-native-command`.
- native tokens are lower than raw and RTK for those cases.
- token-bearing wins remain lane-specific.

- [ ] **Step 3: Run Aql vault benchmark**

Run:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
```

Expected: vault verdict remains `hybrid-only`.

- [ ] **Step 4: Run privacy scan over tracked files and generated report**

Run:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
import subprocess
from flowtrim.privacy import scan_text
root = Path.cwd()
paths = subprocess.run(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
    cwd=root,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
bad = []
for rel in paths:
    path = root / rel
    if path.is_file() and "benchmarks/reports/" not in rel:
        findings = scan_text(path.read_text(errors="ignore"))
        if findings:
            bad.append((rel, findings))
report = Path("/tmp/flowtrim-native-synthetic.json")
if report.exists():
    findings = scan_text(report.read_text(errors="ignore"))
    if findings:
        bad.append((report.name, findings))
print(bad)
raise SystemExit(1 if bad else 0)
PY
```

Expected: `[]`.

- [ ] **Step 5: Run skill validation**

Run:

```bash
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
```

Expected: `Skill is valid!`.

- [ ] **Step 6: Commit**

Run:

```bash
git add README.md docs/benchmark-results.md docs/superpowers/plans/2026-06-18-flowtrim-native-command-output-implementation.md src/flowtrim/scorecard.py src/flowtrim/native_command.py src/flowtrim/benchmark.py tests/test_scorecard.py tests/test_native_command.py tests/test_suite.py tests/test_proof_matrix.py
git commit -m "feat: add native command output compactor"
```

Expected: commit succeeds with only public-safe files.

## Self-Review

Spec coverage:

- Standalone native direction: covered by native command module.
- External baselines optional: covered by keeping RTK fixture replay and comparing native against it.
- Proof that native is better: covered by scorecard tests and synthetic benchmark token comparison.
- Clean-room rule: covered by native parser derived from FlowTrim fixtures and tests only.
- Privacy/runtime gates: covered by existing report gates plus added privacy verification.

Placeholder scan:

- The plan intentionally uses `<AQL_ATLAS_ROOT>` and `<SKILL_CREATOR_QUICK_VALIDATE>` as user-local command placeholders. No implementation details are left unspecified.

Type consistency:

- Native method name is consistently `flowtrim-native-command`.
- Score labels match the approved design.
- Packet keys match `SAFE_PAYLOAD_KEYS` updates.
