import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bounty_tools.cli import main
from bounty_tools.jsoncheck import separate_jsonl, validate_json


class JsonCheckTests(unittest.TestCase):
    def test_valid_json_document(self) -> None:
        result = validate_json(io.StringIO('{"ok": true}'))

        self.assertTrue(result.valid)
        self.assertEqual(result.records_checked, 1)

    def test_invalid_json_reports_line_and_column(self) -> None:
        result = validate_json(io.StringIO('{\n  "ok": }\n'))

        self.assertFalse(result.valid)
        self.assertIn("line 2, column 9", result.errors[0])

    def test_empty_json_document_is_invalid(self) -> None:
        result = validate_json(io.StringIO(""))

        self.assertFalse(result.valid)
        self.assertEqual(result.invalid_records, 1)

    def test_empty_jsonl_stream_is_a_valid_empty_stream(self) -> None:
        result = validate_json(io.StringIO("\n  \n"), jsonl=True)

        self.assertTrue(result.valid)
        self.assertEqual(result.records_checked, 0)

    def test_jsonl_skips_blank_lines_and_checks_each_record(self) -> None:
        result = validate_json(
            io.StringIO('{"id": 1}\n\n{"id": 2}\n'),
            jsonl=True,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.records_checked, 2)

    def test_jsonl_reports_errors_and_caps_error_details(self) -> None:
        result = validate_json(
            io.StringIO('{"ok": true}\ninvalid\nalso invalid\n'),
            jsonl=True,
            max_errors=1,
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.invalid_records, 2)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.omitted_errors, 1)

    def test_jsonl_counts_valid_and_invalid_lines_in_one_pass(self) -> None:
        result = validate_json(
            io.StringIO('{"id": 1}\nnot-json\n{"id": 3}\n[] trailing\n'),
            jsonl=True,
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.records_checked, 4)
        self.assertEqual(result.invalid_records, 2)
        self.assertTrue(result.errors[0].startswith("line 2,"))
        self.assertTrue(result.errors[1].startswith("line 4,"))

    def test_separate_jsonl_writes_valid_records_and_empty_invalid_output(self) -> None:
        valid_output = io.StringIO()
        invalid_output = io.StringIO()

        result = separate_jsonl(
            io.StringIO('{"id": 1}\n{"id": 2}\n'),
            valid_output,
            invalid_output,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.records_checked, 2)
        self.assertEqual(valid_output.getvalue(), '{"id": 1}\n{"id": 2}\n')
        self.assertEqual(invalid_output.getvalue(), "")

    def test_separate_jsonl_records_mixed_line_diagnostics(self) -> None:
        valid_output = io.StringIO()
        invalid_output = io.StringIO()

        result = separate_jsonl(
            io.StringIO('{"id": 1}\n\n{"id": }\n{"id": 4}\n'),
            valid_output,
            invalid_output,
        )

        invalid_records = [
            json.loads(line) for line in invalid_output.getvalue().splitlines()
        ]
        self.assertFalse(result.valid)
        self.assertEqual(result.records_checked, 3)
        self.assertEqual(result.invalid_records, 1)
        self.assertEqual(valid_output.getvalue(), '{"id": 1}\n{"id": 4}\n')
        self.assertEqual(
            invalid_records,
            [
                {
                    "line": 3,
                    "column": 8,
                    "reason": "Expecting value",
                    "raw": '{"id": }',
                }
            ],
        )

    def test_separate_jsonl_empty_stream_creates_empty_outputs(self) -> None:
        valid_output = io.StringIO()
        invalid_output = io.StringIO()

        result = separate_jsonl(
            io.StringIO("\n  \n"),
            valid_output,
            invalid_output,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.records_checked, 0)
        self.assertEqual(valid_output.getvalue(), "")
        self.assertEqual(invalid_output.getvalue(), "")

    def test_cli_reads_from_stdin(self) -> None:
        with patch("sys.stdin", io.StringIO('{"ok": true}\n')):
            self.assertEqual(main(["json-check", "-", "--jsonl"]), 0)

    def test_cli_returns_one_for_invalid_input(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text('{"ok": }\n', encoding="utf-8")

            self.assertEqual(main(["json-check", str(path)]), 1)

    def test_cli_returns_two_for_missing_input(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.json"

            self.assertEqual(main(["json-check", str(path)]), 2)

    def test_cli_returns_two_for_invalid_utf8(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.jsonl"
            path.write_bytes(b'{"ok": true}\n{"text":"\xff"}\n')

            self.assertEqual(main(["json-check", str(path), "--jsonl"]), 2)

    def test_cli_separates_jsonl_with_output_options(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.jsonl"
            valid_path = root / "valid.jsonl"
            invalid_path = root / "invalid.jsonl"
            source.write_text('{"id": 1}\ninvalid\n', encoding="utf-8")

            status = main(
                [
                    "json-check",
                    str(source),
                    "--jsonl",
                    "--valid-out",
                    str(valid_path),
                    "--invalid-out",
                    str(invalid_path),
                ]
            )

            invalid_record = json.loads(
                invalid_path.read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertEqual(status, 1)
            self.assertEqual(valid_path.read_text(encoding="utf-8"), '{"id": 1}\n')
            self.assertEqual(invalid_record["line"], 2)
            self.assertEqual(invalid_record["column"], 1)
            self.assertEqual(invalid_record["reason"], "Expecting value")
            self.assertEqual(invalid_record["raw"], "invalid")

    def test_cli_rejects_output_options_without_jsonl(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.json"
            source.write_text('{"id": 1}\n', encoding="utf-8")

            with self.assertRaises(SystemExit) as raised:
                main(
                    [
                        "json-check",
                        str(source),
                        "--valid-out",
                        str(root / "valid.jsonl"),
                        "--invalid-out",
                        str(root / "invalid.jsonl"),
                    ]
                )

            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
