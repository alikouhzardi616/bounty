from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bounty_tools.cli import main
from bounty_tools.duplicates import find_duplicates, sha256_file


class DuplicateTests(unittest.TestCase):
    def test_finds_duplicate_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.txt").write_text("same content", encoding="utf-8")
            (root / "two.txt").write_text("same content", encoding="utf-8")
            (root / "unique.txt").write_text("different", encoding="utf-8")

            groups = find_duplicates(root)

            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["count"], 2)
            self.assertEqual(len(groups[0]["paths"]), 2)

    def test_min_size_excludes_small_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.txt").write_text("aa", encoding="utf-8")
            (root / "two.txt").write_text("aa", encoding="utf-8")

            self.assertEqual(find_duplicates(root, min_size=3), [])

    def test_missing_directory_returns_error_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            status = main(["duplicate", str(missing)])
            self.assertEqual(status, 2)

    def test_json_output_is_created(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.txt").write_text("same", encoding="utf-8")
            (root / "two.txt").write_text("same", encoding="utf-8")
            output = root / "report.json"

            status = main(
                [
                    "duplicate",
                    str(root),
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(status, 0)
            self.assertIn('"sha256"', output.read_text(encoding="utf-8"))

    def test_sha256_is_deterministic(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "file.txt"
            path.write_bytes(b"content")
            self.assertEqual(
                sha256_file(path),
                "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73",
            )


if __name__ == "__main__":
    unittest.main()
