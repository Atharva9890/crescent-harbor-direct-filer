from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Callable

from .config import ROOT
from .utils import age_on_date, has_more_than_two_decimal_places, quantize_cents


@dataclass(frozen=True)
class RuleIssue:
    rule_id: str
    severity: str
    path: str
    message: str


class RulesEngine:
    def __init__(self, rules_path: Path | None = None) -> None:
        path = rules_path or ROOT / "rules" / "rules.json"
        with path.open() as handle:
            payload = json.load(handle)
        self.rules = payload["rules"]
        self.custom_checks: dict[str, Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], list[RuleIssue]]] = {
            "rfc5322EmailAddrSpec": self._check_email,
            "imoCheckDigit": self._check_imo,
            "vesselTypeTerminalConsistent": self._check_vessel_terminal,
            "containerIdUniqueness": self._check_container_uniqueness,
            "ballastExclusivity": self._check_ballast_exclusivity,
            "vinListMatchesQuantity": self._check_vin_length,
            "class7RequiresPriorAuth": self._check_class7_prior_auth,
            "hazmatProportionUnderQuarter": self._check_hazmat_weight,
            "hazmatPresenceWarning": self._check_hazmat_presence,
            "declaredValueTotalMatchesSum": self._check_declared_total,
            "twoDecimalPlacePrecision": self._check_value_precision,
            "exactlyOneMaster": self._check_exactly_one_master,
            "crewAgeRange": self._check_crew_age,
            "masterHasNationality": self._check_master_nationality,
            "filingNotTooEarly": self._check_not_too_early,
            "filingNotTooLate": self._check_not_too_late,
            "amendmentInvariants": self._check_amendment_invariants,
            "amendmentSequenceMonotonic": self._check_amendment_sequence,
        }

    def evaluate(self, manifest: dict[str, Any], context: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        for rule in self.rules:
            check = rule["check"]
            check_type = check["type"]
            if check_type == "regex":
                issues.extend(self._apply_regex(rule, manifest))
            elif check_type == "minValue":
                issues.extend(self._apply_min_value(rule, manifest))
            elif check_type == "maxValue":
                issues.extend(self._apply_max_value(rule, manifest))
            elif check_type == "minItems":
                issues.extend(self._apply_min_items(rule, manifest))
            elif check_type == "notEquals":
                issues.extend(self._apply_not_equals(rule, manifest))
            elif check_type == "custom":
                issues.extend(self.custom_checks[check["name"]](rule, manifest, context))
        return issues

    def _issue(self, rule: dict[str, Any], path: str, message: str) -> RuleIssue:
        return RuleIssue(rule_id=rule["id"], severity=rule["severity"], path=path, message=message)

    def _lookup(self, manifest: dict[str, Any], pointer: str) -> Any:
        if pointer == "/":
            return manifest
        value: Any = manifest
        for part in pointer.strip("/").split("/"):
            if isinstance(value, list):
                value = value[int(part)]
            else:
                value = value.get(part)
        return value

    def _apply_regex(self, rule: dict[str, Any], manifest: dict[str, Any]) -> list[RuleIssue]:
        value = self._lookup(manifest, rule["field"])
        if not isinstance(value, str) or not re.fullmatch(rule["check"]["pattern"], value):
            return [self._issue(rule, rule["field"], f"{rule['field']} failed format check")]
        return []

    def _apply_min_value(self, rule: dict[str, Any], manifest: dict[str, Any]) -> list[RuleIssue]:
        value = self._lookup(manifest, rule["field"])
        if value < rule["check"]["value"]:
            return [self._issue(rule, rule["field"], f"value must be at least {rule['check']['value']}")]
        return []

    def _apply_max_value(self, rule: dict[str, Any], manifest: dict[str, Any]) -> list[RuleIssue]:
        value = self._lookup(manifest, rule["field"])
        if value > rule["check"]["value"]:
            return [self._issue(rule, rule["field"], f"value must be at most {rule['check']['value']}")]
        return []

    def _apply_min_items(self, rule: dict[str, Any], manifest: dict[str, Any]) -> list[RuleIssue]:
        value = self._lookup(manifest, rule["field"])
        if len(value) < rule["check"]["value"]:
            return [self._issue(rule, rule["field"], f"must contain at least {rule['check']['value']} item(s)")]
        return []

    def _apply_not_equals(self, rule: dict[str, Any], manifest: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        for index, container in enumerate(manifest["containers"]):
            if container["type"] == "REF" and container.get("commodityCode") == rule["check"]["value"]:
                issues.append(self._issue(rule, f"/containers/{index}/commodityCode", 'reserved value "0000" is not allowed'))
        return issues

    def _check_email(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        value = manifest["filer"]["contactEmail"]
        _, parsed = parseaddr(value)
        if not parsed or parsed != value or "@" not in value:
            return [self._issue(rule, rule["field"], "contactEmail is not syntactically valid")]
        return []

    def _check_imo(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        digits = manifest["vessel"]["imoNumber"].replace("IMO", "")
        checksum = sum(int(digit) * weight for digit, weight in zip(digits[:6], [7, 6, 5, 4, 3, 2])) % 10
        if checksum != int(digits[6]):
            return [self._issue(rule, rule["field"], "IMO check digit is invalid")]
        return []

    def _check_vessel_terminal(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        vessel_type = manifest["vessel"]["vesselType"]
        terminal = manifest["arrival"]["terminal"]
        allowed = {
            "CONTAINER": {"CH-A", "CH-B"},
            "BULK": {"CH-C"},
            "TANKER": {"CH-C"},
            "RORO": {"CH-D"},
            "GENERAL": {"CH-A", "CH-B", "CH-C", "CH-D"},
        }
        if terminal not in allowed[vessel_type]:
            return [self._issue(rule, "/arrival/terminal", f"{vessel_type} vessels cannot arrive at {terminal}")]
        return []

    def _check_container_uniqueness(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        seen: dict[str, int] = {}
        issues: list[RuleIssue] = []
        for index, container in enumerate(manifest["containers"]):
            container_id = container["containerId"]
            if container_id in seen:
                issues.append(self._issue(rule, f"/containers/{index}/containerId", f"duplicate containerId also seen at index {seen[container_id]}"))
            seen[container_id] = index
        return issues

    def _check_ballast_exclusivity(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        ballast_indexes = [index for index, container in enumerate(manifest["containers"]) if container["type"] == "BALLAST"]
        issues: list[RuleIssue] = []
        if ballast_indexes and len(manifest["containers"]) != 1:
            for index in ballast_indexes:
                issues.append(self._issue(rule, f"/containers/{index}", "BALLAST may only appear as the sole container"))
        return issues

    def _check_vin_length(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        for index, container in enumerate(manifest["containers"]):
            if container["type"] == "VEH" and len(container.get("vins", [])) != container["quantity"]:
                issues.append(self._issue(rule, f"/containers/{index}/vins", "VIN count must equal quantity"))
        return issues

    def _check_class7_prior_auth(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        for index, container in enumerate(manifest["containers"]):
            if container["type"] == "HAZ" and container.get("hazardClass") == "7" and not container.get("priorAuthorizationRef"):
                issues.append(self._issue(rule, f"/containers/{index}/priorAuthorizationRef", "class 7 hazmat requires priorAuthorizationRef"))
        return issues

    def _check_hazmat_weight(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        hazmat_containers = [container for container in manifest["containers"] if container["type"] == "HAZ"]
        if not hazmat_containers:
            return []
        known_weights = [container.get("grossWeightKg") for container in hazmat_containers if container.get("grossWeightKg") is not None]
        if len(known_weights) != len(hazmat_containers):
            return []
        hazmat_weight_tons = sum(known_weights) / 1000
        if hazmat_weight_tons > manifest["vessel"]["grossRegisterTons"] * 0.25:
            return [self._issue(rule, "/containers", "combined hazmat gross weight exceeds 25% of vessel gross register tons")]
        return []

    def _check_hazmat_presence(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        if any(container["type"] == "HAZ" for container in manifest["containers"]):
            return [self._issue(rule, "/containers", "hazmat present; flagging for harbormaster review")]
        return []

    def _check_declared_total(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        expected = sum(quantize_cents(container["declaredValueUSD"]) for container in manifest["containers"])
        actual = quantize_cents(manifest["declaredValueTotal"])
        if actual != expected:
            return [self._issue(rule, "/declaredValueTotal", f"declaredValueTotal {actual} does not match computed total {expected}")]
        return []

    def _check_value_precision(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        for index, container in enumerate(manifest["containers"]):
            if has_more_than_two_decimal_places(container["declaredValueUSD"]):
                issues.append(self._issue(rule, f"/containers/{index}/declaredValueUSD", "value has more than two decimal places"))
        return issues

    def _check_exactly_one_master(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        masters = [member for member in manifest["crew"] if member["role"] == "MASTER"]
        if len(masters) != 1:
            return [self._issue(rule, "/crew", "exactly one crew member must have role MASTER")]
        return []

    def _check_crew_age(self, rule: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]) -> list[RuleIssue]:
        issues: list[RuleIssue] = []
        eta = context["eta"]
        for index, member in enumerate(manifest["crew"]):
            age = age_on_date(member["dateOfBirth"], eta)
            if age < 16 or age > 80:
                issues.append(self._issue(rule, f"/crew/{index}/dateOfBirth", f"crew member age {age} is outside the permitted range"))
        return issues

    def _check_master_nationality(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        for index, member in enumerate(manifest["crew"]):
            if member["role"] == "MASTER" and not member.get("nationality"):
                return [self._issue(rule, f"/crew/{index}/nationality", "MASTER must have a nationality")]
        return []

    def _check_not_too_early(self, rule: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]) -> list[RuleIssue]:
        delta_hours = (context["eta"] - context["built_at"]).total_seconds() / 3600
        if delta_hours > 96:
            return [self._issue(rule, "/arrival/eta", "manifest is being transmitted more than 96 hours before ETA")]
        return []

    def _check_not_too_late(self, rule: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]) -> list[RuleIssue]:
        delta_hours = (context["eta"] - context["built_at"]).total_seconds() / 3600
        if delta_hours < 24:
            return [self._issue(rule, "/arrival/eta", "manifest is being transmitted fewer than 24 hours before ETA")]
        return []

    def _check_amendment_invariants(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        if "amendmentSequence" in manifest:
            return [self._issue(rule, "/amendmentSequence", "amendments require persisted original-manifest state, which is not available in this stateless case-study filer")]
        return []

    def _check_amendment_sequence(self, rule: dict[str, Any], manifest: dict[str, Any], _: dict[str, Any]) -> list[RuleIssue]:
        if "amendmentSequence" in manifest and manifest["amendmentSequence"] < 1:
            return [self._issue(rule, "/amendmentSequence", "first amendment sequence must be 1")]
        return []
