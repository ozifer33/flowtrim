import json
import unittest

from flowtrim.benchmark import (
    BenchmarkCase,
    BenchmarkStatus,
    MethodMeasurement,
    MetricFamily,
    PreservationSummary,
    RuntimeChanges,
    ToolInfo,
    build_report,
    evaluate_case,
    report_to_json,
)
from flowtrim.models import Lane


def measurement(
    method,
    tokens,
    *,
    status=BenchmarkStatus.OK,
    wall_time_ms=10,
    timeout=False,
    guard_passed=True,
    reason=None,
):
    return MethodMeasurement(
        method=method,
        status=status,
        tokens=tokens,
        wall_time_ms=wall_time_ms,
        timeout=timeout,
        repeat_count=3,
        guard_passed=guard_passed,
        reason=reason,
    )


def case(
    *,
    case_id="case-1",
    lane=Lane.COMMAND_OUTPUT,
    metric_family=MetricFamily.TOKEN_BEARING,
    methods=None,
    preservation=True,
    fixture="inline.txt",
):
    return BenchmarkCase(
        case_id=case_id,
        lane=lane,
        fixture=fixture,
        metric_family=metric_family,
        methods=methods
        or [
            measurement("raw", 100),
            measurement("flowtrim-selected", 40),
        ],
        preservation=PreservationSummary(passed=preservation, missing_items=[]),
        runtime_changes=RuntimeChanges(),
    )


class BenchmarkGateTest(unittest.TestCase):
    def test_token_bearing_candidate_counts_as_win_only_when_all_gates_pass(self):
        evaluated = evaluate_case(case())

        self.assertEqual(evaluated.selected_method, "flowtrim-selected")
        self.assertEqual(evaluated.winner, "flowtrim-selected")
        self.assertTrue(evaluated.counts_as_claim)

        failing_variants = {
            "not-fewer-tokens": measurement("flowtrim-selected", 100),
            "preservation-fails": measurement("flowtrim-selected", 40),
            "timeout": measurement("flowtrim-selected", 40, timeout=True),
            "over-budget": measurement("flowtrim-selected", 40, wall_time_ms=251),
        }
        for name, candidate in failing_variants.items():
            with self.subTest(name=name):
                preservation = name != "preservation-fails"
                evaluated = evaluate_case(
                    case(methods=[measurement("raw", 100), candidate], preservation=preservation)
                )

                self.assertNotEqual(evaluated.winner, "flowtrim-selected")
                self.assertFalse(evaluated.counts_as_claim)

    def test_short_and_zero_token_raw_command_output_wins_over_non_raw(self):
        for raw_tokens in (0, 3):
            with self.subTest(raw_tokens=raw_tokens):
                evaluated = evaluate_case(
                    case(
                        methods=[
                            measurement("raw", raw_tokens),
                            measurement("flowtrim-selected", max(raw_tokens - 1, 0)),
                        ]
                    )
                )

                self.assertEqual(evaluated.selected_method, "raw")
                self.assertEqual(evaluated.winner, "raw")
                self.assertFalse(evaluated.counts_as_claim)

    def test_exact_evidence_always_selects_raw_and_counts_correct_refusal(self):
        evaluated = evaluate_case(
            case(
                lane=Lane.EXACT_EVIDENCE,
                metric_family=MetricFamily.REFUSAL_CORRECTNESS,
                methods=[
                    measurement("raw", 500),
                    measurement("unsafe-summary", 5, guard_passed=False),
                ],
            )
        )

        self.assertEqual(evaluated.selected_method, "raw")
        self.assertEqual(evaluated.winner, "raw")
        self.assertEqual(evaluated.decision_reason, "correct-refusal")

        report = build_report("synthetic-heavy", [evaluated], [], [])

        self.assertEqual(
            report.metric_totals["refusal-correctness"]["correct_refusals"], 1
        )
        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)

    def test_skipped_methods_are_reported_and_cannot_be_selected(self):
        evaluated = evaluate_case(
            case(
                methods=[
                    measurement("raw", 100),
                    measurement(
                        "headroom-direct",
                        1,
                        status=BenchmarkStatus.SKIPPED,
                        reason="not installed",
                    ),
                ]
            )
        )

        skipped = next(method for method in evaluated.methods if method.method == "headroom-direct")
        self.assertEqual(skipped.status, BenchmarkStatus.SKIPPED)
        self.assertEqual(evaluated.selected_method, "raw")
        self.assertNotEqual(evaluated.winner, "headroom-direct")

    def test_guard_failure_yields_insufficient_evidence_without_positive_savings(self):
        evaluated = evaluate_case(
            case(
                methods=[
                    measurement("raw", 100),
                    measurement("flowtrim-selected", 10, guard_passed=False),
                ]
            )
        )

        self.assertEqual(evaluated.selected_method, "raw")
        self.assertEqual(evaluated.winner, "insufficient-evidence")
        self.assertFalse(evaluated.counts_as_claim)

        report = build_report("synthetic-heavy", [evaluated], [], [])

        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)
        self.assertEqual(report.metric_totals["token-bearing"]["tokens_saved"], 0)
        self.assertEqual(report.metric_totals["token-bearing"]["insufficient_evidence"], 1)

    def test_invalid_raw_baseline_cannot_produce_a_win_or_refusal(self):
        for lane, metric_family in (
            (Lane.COMMAND_OUTPUT, MetricFamily.TOKEN_BEARING),
            (Lane.EXACT_EVIDENCE, MetricFamily.REFUSAL_CORRECTNESS),
        ):
            with self.subTest(lane=lane):
                evaluated = evaluate_case(
                    case(
                        lane=lane,
                        metric_family=metric_family,
                        methods=[
                            measurement("raw", 100, status=BenchmarkStatus.SKIPPED),
                            measurement("flowtrim-selected", 10),
                        ],
                    )
                )

                self.assertIsNone(evaluated.selected_method)
                self.assertEqual(evaluated.winner, "insufficient-evidence")
                self.assertFalse(evaluated.counts_as_claim)

    def test_exact_evidence_still_requires_preservation_and_no_runtime_changes(self):
        preservation_failure = evaluate_case(
            case(
                lane=Lane.EXACT_EVIDENCE,
                metric_family=MetricFamily.REFUSAL_CORRECTNESS,
                preservation=False,
                methods=[
                    measurement("raw", 500),
                    measurement("unsafe-summary", 5, guard_passed=False),
                ],
            )
        )

        self.assertEqual(preservation_failure.winner, "insufficient-evidence")
        self.assertNotEqual(preservation_failure.decision_reason, "correct-refusal")

        runtime_failure = evaluate_case(
            BenchmarkCase(
                case_id="exact-runtime-change",
                lane=Lane.EXACT_EVIDENCE,
                fixture="inline.txt",
                metric_family=MetricFamily.REFUSAL_CORRECTNESS,
                methods=[measurement("raw", 500)],
                preservation=PreservationSummary(passed=True),
                runtime_changes=RuntimeChanges(config_writes=True),
            )
        )

        self.assertEqual(runtime_failure.winner, "insufficient-evidence")
        self.assertNotEqual(runtime_failure.decision_reason, "correct-refusal")

    def test_build_report_reevaluates_preselected_cases_before_counting_claims(self):
        preselected_bad_case = BenchmarkCase(
            case_id="preselected-bad",
            lane=Lane.COMMAND_OUTPUT,
            fixture="inline.txt",
            metric_family=MetricFamily.TOKEN_BEARING,
            methods=[
                measurement("raw", 100),
                measurement("flowtrim-selected", 10),
            ],
            preservation=PreservationSummary(passed=False, missing_items=["src/app.py"]),
            runtime_changes=RuntimeChanges(),
            selected_method="flowtrim-selected",
            winner="flowtrim-selected",
            counts_as_claim=True,
            decision_reason="caller-provided",
        )

        report = build_report("synthetic-heavy", [preselected_bad_case], [], [])

        self.assertEqual(report.cases[0].winner, "insufficient-evidence")
        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)

    def test_code_lens_rejects_must_keep_requirement_and_test_surface_violations(self):
        unsafe_payloads = [
            {"must_keep_violation": True},
            {"requirements_preserved": False},
            {"test_surface_preserved": False},
        ]

        for payload in unsafe_payloads:
            with self.subTest(payload=payload):
                evaluated = evaluate_case(
                    case(
                        lane=Lane.CODE_GENERATION,
                        metric_family=MetricFamily.CODE_LENS,
                        methods=[
                            measurement("baseline-code", 500),
                            MethodMeasurement(
                                method="ponytail-lens",
                                status=BenchmarkStatus.OK,
                                tokens=300,
                                wall_time_ms=20,
                                timeout=False,
                                repeat_count=3,
                                guard_passed=True,
                                payload=payload,
                            ),
                            measurement("raw", 500),
                        ],
                    )
                )

                self.assertEqual(evaluated.winner, "insufficient-evidence")
                self.assertFalse(evaluated.counts_as_claim)

        nested = evaluate_case(
            case(
                lane=Lane.CODE_GENERATION,
                metric_family=MetricFamily.CODE_LENS,
                methods=[
                    measurement("baseline-code", 500),
                    MethodMeasurement(
                        method="ponytail-lens",
                        status=BenchmarkStatus.OK,
                        tokens=300,
                        wall_time_ms=20,
                        timeout=False,
                        repeat_count=3,
                        guard_passed=True,
                        payload={
                            "delete_items": [
                                {
                                    "item": "outer helper",
                                    "delete_items": [
                                        {
                                            "item": "required parser",
                                            "must_keep_violation": True,
                                        }
                                    ],
                                }
                            ]
                        },
                    ),
                    measurement("raw", 500),
                ],
            )
        )

        self.assertEqual(nested.winner, "insufficient-evidence")

    def test_vault_semantic_cases_defer_to_atlas_context_economy(self):
        evaluated = evaluate_case(
            case(
                case_id="vault-packet-routing",
                lane=Lane.LONG_CONTEXT,
                fixture="vault/aql-packet-routing.md",
                metric_family=MetricFamily.VAULT_SEMANTIC,
                methods=[
                    measurement("raw", 400),
                    measurement("flowtrim-selected", 40),
                    measurement("atlas-context-economy", 120),
                ],
            )
        )

        self.assertEqual(evaluated.selected_method, "atlas-context-economy")
        self.assertEqual(evaluated.winner, "atlas-context-economy")
        self.assertFalse(evaluated.counts_as_claim)

        report = build_report("aql-vault-readonly", [evaluated], [], [])

        self.assertEqual(report.vault_verdict, "hybrid-only")

    def test_vault_semantic_deferrals_alone_stay_hybrid_only(self):
        fixtures = [
            "vault/aql-short-command.txt",
            "vault/aql-rtk-candidate.txt",
            "vault/aql-packet-routing.md",
            "vault/aql-index-inventory.md",
            "vault/aql-source-id-preservation.md",
            "vault/aql-approval-boundary.md",
        ]
        cases = [
            evaluate_case(
                case(
                    case_id=f"vault-{index}",
                    lane=Lane.LONG_CONTEXT,
                    fixture=fixture,
                    metric_family=MetricFamily.VAULT_SEMANTIC,
                    methods=[
                        measurement("raw", 400),
                        measurement("atlas-context-economy", 120),
                    ],
                )
            )
            for index, fixture in enumerate(fixtures)
        ]

        report = build_report("aql-vault-readonly", cases, [], [])

        self.assertEqual(report.vault_verdict, "hybrid-only")

    def test_vault_verdict_is_vault_safe_only_with_semantic_deferrals_and_token_win(self):
        fixtures = [
            "vault/aql-short-command.txt",
            "vault/aql-packet-routing.md",
            "vault/aql-index-inventory.md",
            "vault/aql-source-id-preservation.md",
            "vault/aql-approval-boundary.md",
        ]
        cases = [
            evaluate_case(
                case(
                    case_id=f"vault-{index}",
                    lane=Lane.LONG_CONTEXT,
                    fixture=fixture,
                    metric_family=MetricFamily.VAULT_SEMANTIC,
                    methods=[
                        measurement("raw", 400),
                        measurement("atlas-context-economy", 120),
                    ],
                )
            )
            for index, fixture in enumerate(fixtures)
        ]
        cases.append(
            evaluate_case(
                case(
                    case_id="vault-rtk-candidate",
                    lane=Lane.COMMAND_OUTPUT,
                    fixture="vault/aql-rtk-candidate.txt",
                    metric_family=MetricFamily.TOKEN_BEARING,
                    methods=[
                        measurement("raw", 400),
                        measurement("flowtrim-selected", 120),
                    ],
                )
            )
        )

        report = build_report("aql-vault-readonly", cases, [], [])

        self.assertEqual(report.vault_verdict, "vault-safe")

    def test_vault_safe_requires_atlas_semantic_deferrals(self):
        fixtures = [
            "vault/aql-short-command.txt",
            "vault/aql-rtk-candidate.txt",
            "vault/aql-packet-routing.md",
            "vault/aql-index-inventory.md",
            "vault/aql-source-id-preservation.md",
            "vault/aql-approval-boundary.md",
        ]
        cases = [
            evaluate_case(
                case(
                    case_id=f"vault-token-{index}",
                    lane=Lane.COMMAND_OUTPUT,
                    fixture=fixture,
                    metric_family=MetricFamily.TOKEN_BEARING,
                    methods=[
                        measurement("raw", 400),
                        measurement("flowtrim-selected", 100),
                    ],
                )
            )
            for index, fixture in enumerate(fixtures)
        ]

        report = build_report("aql-vault-readonly", cases, [], [])

        self.assertEqual(report.vault_verdict, "hybrid-only")

    def test_report_json_rejects_unsafe_payload_keys(self):
        report = build_report(
            "synthetic-heavy",
            [
                evaluate_case(
                    case(
                        methods=[
                            measurement("raw", 100),
                            measurement(
                                "flowtrim-selected",
                                40,
                                reason="measured",
                            ),
                        ]
                    )
                )
            ],
            [],
            [],
        )
        unsafe_method = report.cases[0].methods[0]
        unsafe_report = report.__class__(
            schema=report.schema,
            profile=report.profile,
            runtime_changes=report.runtime_changes,
            tools=report.tools,
            cases=[
                report.cases[0].__class__(
                    **{
                        **report.cases[0].__dict__,
                        "methods": [
                            unsafe_method.__class__(
                                **{
                                    **unsafe_method.__dict__,
                                    "payload": {"raw_output": "secret raw text"},
                                }
                            )
                        ],
                    }
                )
            ],
            metric_totals=report.metric_totals,
            vault_verdict=report.vault_verdict,
            upgrade_backlog=report.upgrade_backlog,
        )

        with self.assertRaisesRegex(ValueError, "unsafe payload key"):
            report_to_json(unsafe_report)

    def test_report_json_rejects_private_paths_inside_allowed_payload_keys(self):
        report = build_report(
            "synthetic-heavy",
            [evaluate_case(case())],
            [],
            [],
        )
        method = report.cases[0].methods[0]
        unsafe_report = report.__class__(
            schema=report.schema,
            profile=report.profile,
            runtime_changes=report.runtime_changes,
            tools=report.tools,
            cases=[
                report.cases[0].__class__(
                    **{
                        **report.cases[0].__dict__,
                        "methods": [
                            method.__class__(
                                **{
                                    **method.__dict__,
                                    "payload": {
                                        "sanitized_snippet": "/Users/example/project/private.txt"
                                    },
                                }
                            )
                        ],
                    }
                )
            ],
            metric_totals=report.metric_totals,
            vault_verdict=report.vault_verdict,
            upgrade_backlog=report.upgrade_backlog,
        )

        with self.assertRaisesRegex(ValueError, "unsafe payload value"):
            report_to_json(unsafe_report)

    def test_report_json_contains_required_top_level_sections(self):
        report = build_report(
            "synthetic-heavy",
            [evaluate_case(case())],
            [ToolInfo(name="rtk", available=False, reason="not installed")],
            ["capture Headroom version when available"],
        )

        data = json.loads(report_to_json(report))

        self.assertEqual(
            list(data),
            [
                "cases",
                "metric_totals",
                "profile",
                "runtime_changes",
                "schema",
                "tools",
                "upgrade_backlog",
                "vault_verdict",
            ],
        )
        self.assertEqual(data["schema"], "flowtrim-benchmark/v1")
        self.assertEqual(data["profile"], "synthetic-heavy")
        self.assertEqual(data["vault_verdict"], "not-vault")
        self.assertIn("generated_loc_delta", data["metric_totals"]["code-lens"])
        self.assertIn("delete_items", data["metric_totals"]["code-lens"])
        self.assertIn("duplicate_abstractions", data["metric_totals"]["code-lens"])


if __name__ == "__main__":
    unittest.main()
