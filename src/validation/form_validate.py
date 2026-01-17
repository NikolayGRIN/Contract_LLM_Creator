from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import ValidationError


@dataclass
class ValidationIssue:
    path: str
    message: str


def _format_path(error: ValidationError) -> str:
    if not error.path:
        return "$"
    parts = []
    for p in list(error.path):
        if isinstance(p, int):
            parts.append(f"[{p}]")
        else:
            parts.append(p if not parts else f".{p}")
    return "$." + "".join(parts).lstrip(".")


def _collect_issues(errors: List[ValidationError]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for err in errors:
        issues.append(ValidationIssue(path=_format_path(err), message=err.message))
    issues.sort(key=lambda x: x.path)
    return issues


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"File not found: {path}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {path}: {e}")


def validate_form(form_data: dict, schema_path: Path, base_dir: Optional[Path] = None):
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(form_data))
    return _collect_issues(errors)


def main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate Contract Form v1 JSON against JSON Schema.")
    parser.add_argument("--input", required=True, help="Path to form_input.json")
    parser.add_argument(
        "--schema",
        default="src/form_schema/contract_form_v1.schema.json",
        help="Path to contract_form_v1.schema.json",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    schema_path = Path(args.schema)

    try:
        form_data = load_json(input_path)
        if not isinstance(form_data, dict):
            print("ERROR: form_input must be a JSON object at the root.", file=sys.stderr)
            return 1

        issues = validate_form(form_data, schema_path=schema_path)

        if issues:
            print(f"❌ INVALID form input: {len(issues)} issue(s) found", file=sys.stderr)
            for i, issue in enumerate(issues, start=1):
                print(f"  {i}. {issue.path}: {issue.message}", file=sys.stderr)
            return 1

        print("✅ VALID form input")
        return 0

    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
