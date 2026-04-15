from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .config import ROOT


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: str


class SchemaValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        path = schema_path or ROOT / "schema" / "manifest.schema.json"
        with path.open() as handle:
            schema = json.load(handle)
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, manifest: dict) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for error in sorted(self._validator.iter_errors(manifest), key=lambda err: list(err.absolute_path)):
            path = "/" + "/".join(str(part) for part in error.absolute_path) if error.absolute_path else "/"
            message = error.message
            if "Additional properties" in message:
                code = "M-103"
            elif "is a required property" in message:
                code = "R-602"
            else:
                code = "M-102"
            issues.append(ValidationIssue(path=path, message=message, code=code))
        return issues
