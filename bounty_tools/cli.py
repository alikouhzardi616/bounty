from __future__ import annotations

import argparse
import csv
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

from .duplicates import find_duplicates
from .jsoncheck import separate_jsonl, validate_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bounty-tools",
        description="Small automation utilities for paid, practical work.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    duplicate_parser = subparsers.add_parser(
        "duplicate",
        help="Report groups of identical files.",
    )
    duplicate_parser.add_argument("path", help="Directory to scan.")
    duplicate_parser.add_argument(
        "--min-size",
        type=_non_negative_int,
        default=0,
        help="Minimum file size in bytes.",
    )
    duplicate_parser.add_argument(
        "--format",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format.",
    )
    duplicate_parser.add_argument(
        "--output",
        help="Write output to this file instead of stdout.",
    )

    json_parser = subparsers.add_parser(
        "json-check",
        help="Validate a JSON document or JSON Lines file.",
    )
    json_parser.add_argument("path", help="Input file, or '-' to read from stdin.")
    json_parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Validate one JSON value per non-empty line.",
    )
    json_parser.add_argument(
        "--max-errors",
        type=_positive_int,
        default=20,
        help="Maximum syntax errors to print for JSON Lines (default: 20).",
    )
    json_parser.add_argument(
        "--valid-out",
        help="Write valid JSONL records to this file (requires --invalid-out).",
    )
    json_parser.add_argument(
        "--invalid-out",
        help="Write invalid records with line/column diagnostics as JSONL "
        "(requires --valid-out).",
    )
    return parser


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _positive_int(value: str) -> int:
    number = _non_negative_int(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "json-check":
        has_outputs = args.valid_out is not None or args.invalid_out is not None
        if (args.valid_out is None) != (args.invalid_out is None):
            parser.error("--valid-out and --invalid-out must be used together")
        if has_outputs and not args.jsonl:
            parser.error("--valid-out and --invalid-out require --jsonl")
        return _run_json_check(
            args.path,
            args.jsonl,
            args.max_errors,
            args.valid_out,
            args.invalid_out,
        )

    try:
        groups = find_duplicates(args.path, min_size=args.min_size)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    output: TextIO
    should_close = False
    if args.output:
        output = Path(args.output).expanduser().open(
            "w",
            encoding="utf-8",
            newline="",
        )
        should_close = True
    else:
        output = sys.stdout

    try:
        if args.format == "json":
            json.dump(groups, output, ensure_ascii=False, indent=2)
            output.write("\n")
        elif args.format == "csv":
            writer = csv.writer(output)
            writer.writerow(["sha256", "size", "count", "path"])
            for group in groups:
                for path in group["paths"]:
                    writer.writerow(
                        [group["sha256"], group["size"], group["count"], path]
                    )
        else:
            _write_table(output, groups)
    finally:
        if should_close:
            output.close()

    return 0


def _run_json_check(
    path: str,
    jsonl: bool,
    max_errors: int,
    valid_out: str | None = None,
    invalid_out: str | None = None,
) -> int:
    input_path = Path(path).expanduser() if path != "-" else None
    output_paths = [
        Path(output_path).expanduser()
        for output_path in (valid_out, invalid_out)
        if output_path is not None
    ]
    try:
        resolved_outputs = [output_path.resolve() for output_path in output_paths]
        if len(set(resolved_outputs)) != len(resolved_outputs):
            print("Error: valid and invalid outputs must be different files.", file=sys.stderr)
            return 2
        if input_path is not None and input_path.resolve() in resolved_outputs:
            print("Error: output files must not overwrite the input.", file=sys.stderr)
            return 2
    except (OSError, RuntimeError) as exc:
        print(f"Error: cannot resolve input/output path: {exc}", file=sys.stderr)
        return 2

    try:
        with ExitStack() as stack:
            input_stream: TextIO
            if input_path is None:
                input_stream = sys.stdin
            else:
                input_stream = stack.enter_context(
                    input_path.open("r", encoding="utf-8")
                )

            valid_output = (
                stack.enter_context(
                    output_paths[0].open("w", encoding="utf-8", newline="\n")
                )
                if valid_out is not None
                else None
            )
            invalid_output = (
                stack.enter_context(
                    output_paths[1].open("w", encoding="utf-8", newline="\n")
                )
                if invalid_out is not None
                else None
            )

            try:
                if valid_output is not None and invalid_output is not None:
                    result = separate_jsonl(
                        input_stream,
                        valid_output,
                        invalid_output,
                        max_errors=max_errors,
                    )
                else:
                    result = validate_json(
                        input_stream,
                        jsonl=jsonl,
                        max_errors=max_errors,
                    )
            except UnicodeDecodeError as exc:
                print(
                    f"Error: input is not valid UTF-8 at byte {exc.start}",
                    file=sys.stderr,
                )
                return 2
            except OSError as exc:
                print(f"Error: cannot write JSONL outputs: {exc}", file=sys.stderr)
                return 2
    except OSError as exc:
        print(f"Error: cannot open input or output: {exc}", file=sys.stderr)
        return 2

    kind = "JSON Lines" if jsonl else "JSON"
    if result.valid:
        print(f"Valid {kind}: {result.records_checked} record(s) checked.")
        return 0

    for error in result.errors:
        print(f"Invalid {kind}: {error}", file=sys.stderr)
    if result.omitted_errors:
        print(
            f"... {result.omitted_errors} additional error(s) omitted.",
            file=sys.stderr,
        )
    print(
        f"{result.invalid_records} invalid record(s) out of "
        f"{result.records_checked} checked.",
        file=sys.stderr,
    )
    return 1


def _write_table(output: TextIO, groups: list[dict[str, object]]) -> None:
    if not groups:
        output.write("No duplicate files found.\n")
        return

    output.write(f"{len(groups)} duplicate group(s)\n")
    for index, group in enumerate(groups, start=1):
        output.write(
            f"\n{index}. {group['count']} files, "
            f"{group['size']} bytes, SHA-256 {group['sha256']}\n"
        )
        for path in group["paths"]:
            output.write(f"  - {path}\n")
