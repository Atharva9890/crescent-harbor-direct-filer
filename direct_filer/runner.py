from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .builder import build_manifest
from .client import AuthorityClient
from .config import ROOT, load_config
from .rules_engine import RuleIssue, RulesEngine
from .schema_validation import SchemaValidator


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    outcome: str
    manifestId: str | None = None
    receiptId: str | None = None
    schemaErrors: list[dict[str, str]] | None = None
    ruleErrors: list[dict[str, str]] | None = None
    warnings: list[dict[str, str]] | None = None
    authorityErrors: list[dict[str, Any]] | None = None
    error: str | None = None


class ScenarioRunner:
    def __init__(self) -> None:
        self.config = load_config()
        self.schema_validator = SchemaValidator()
        self.rules_engine = RulesEngine()
        self.client = AuthorityClient(self.config)

    def run_scenario(self, scenario_path: Path) -> ScenarioResult:
        with scenario_path.open() as handle:
            scenario = json.load(handle)

        manifest, context = build_manifest(scenario, self.config)
        schema_issues = self.schema_validator.validate(manifest)
        if schema_issues:
            return ScenarioResult(
                scenario=context["scenario_id"],
                outcome="rejected_by_schema",
                manifestId=manifest["manifestId"],
                schemaErrors=[asdict(issue) for issue in schema_issues],
            )

        rule_issues = self.rules_engine.evaluate(manifest, context)
        reject_issues = [issue for issue in rule_issues if issue.severity == "reject"]
        warning_issues = [issue for issue in rule_issues if issue.severity == "warning"]
        if reject_issues:
            return ScenarioResult(
                scenario=context["scenario_id"],
                outcome="rejected_by_rules",
                manifestId=manifest["manifestId"],
                ruleErrors=[asdict(issue) for issue in reject_issues],
                warnings=[asdict(issue) for issue in warning_issues] or None,
            )

        try:
            submission = self.client.submit_manifest(manifest)
            ack = self.client.poll_ack(submission.receipt_id or "")
        except Exception as exc:  # pragma: no cover - operational path
            return ScenarioResult(
                scenario=context["scenario_id"],
                outcome="error",
                manifestId=manifest["manifestId"],
                warnings=[asdict(issue) for issue in warning_issues] or None,
                error=str(exc),
            )

        if ack.status == "ACCEPTED":
            return ScenarioResult(
                scenario=context["scenario_id"],
                outcome="accepted",
                manifestId=manifest["manifestId"],
                receiptId=ack.receipt_id,
                warnings=[asdict(issue) for issue in warning_issues] or None,
            )
        return ScenarioResult(
            scenario=context["scenario_id"],
            outcome="rejected_by_authority",
            manifestId=manifest["manifestId"],
            receiptId=ack.receipt_id,
            warnings=[asdict(issue) for issue in warning_issues] or None,
            authorityErrors=ack.errors,
        )

    def run_all(self, scenarios_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
        directory = scenarios_dir or ROOT / "scenarios"
        results = [asdict(self.run_scenario(path)) for path in sorted(directory.glob("*.json"))]
        return {"results": results}
