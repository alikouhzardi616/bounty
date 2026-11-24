from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class ValidationResult:
    records_checked: int = 0
    invalid_records: int = 0
    errors: list[str] = field(default_factory=list)
    omitted_errors: int = 0

    @property
    def valid(self) -> bool:
        return self.invalid_records == 0


@dataclass(frozen=True)
class JsonlDiagnostic:
    line: int
    column: int
    reason: str
    raw: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "line": self.line,
            "column": self.column,
            "reason": self.reason,
            "raw": self.raw,
        }


def validate_json(
    stream: TextIO,
    *,
    jsonl: bool = False,
    max_errors: int = 20,
) -> ValidationResult:
    if max_errors < 1:
        raise ValueError("max_errors must be at least 1")

    result = ValidationResult()
    if not jsonl:
        try:
            json.load(stream)
            result.records_checked = 1
        except json.JSONDecodeError as exc:
            result.records_checked = 1
            result.invalid_records = 1
            result.errors.append(
                f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
            )
        return result

    return _validate_jsonl(stream, max_errors=max_errors)


def separate_jsonl(
    stream: TextIO,
    valid_output: TextIO,
    invalid_output: TextIO,
    *,
    max_errors: int = 20,
) -> ValidationResult:
    """Write valid lines unchanged and invalid lines as diagnostic JSONL records."""
    if max_errors < 1:
        raise ValueError("max_errors must be at least 1")

    return _validate_jsonl(
        stream,
        max_errors=max_errors,
        valid_output=valid_output,
        invalid_output=invalid_output,
    )


def _validate_jsonl(
    stream: TextIO,
    *,
    max_errors: int,
    valid_output: TextIO | None = None,
    invalid_output: TextIO | None = None,
) -> ValidationResult:
    result = ValidationResult()
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        result.records_checked += 1
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            result.invalid_records += 1
            message = f"line {line_number}, column {exc.colno}: {exc.msg}"
            if len(result.errors) < max_errors:
                result.errors.append(message)
            else:
                result.omitted_errors += 1
            if invalid_output is not None:
                diagnostic = JsonlDiagnostic(
                    line=line_number,
                    column=exc.colno,
                    reason=exc.msg,
                    raw=line.rstrip("\r\n"),
                )
                json.dump(diagnostic.as_dict(), invalid_output, ensure_ascii=False)
                invalid_output.write("\n")
        else:
            if valid_output is not None:
                valid_output.write(line)
                if not line.endswith(("\n", "\r")):
                    valid_output.write("\n")

    return result
