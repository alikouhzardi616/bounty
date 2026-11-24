# Work Log

## 2026-11-24

### Built

Created a dependency-free duplicate-file reporter:

- CLI entry point: `python -m bounty_tools duplicate <directory>`
- JSON and CSV reports
- Minimum-size filter
- SHA-256 verification
- Read-only behavior; it never deletes or edits files
- Unit tests in `tests/test_duplicates.py`

### How it works

The scanner groups candidates by file size, hashes matching-size candidates with SHA-256, and outputs every group containing more than one file. It skips missing, inaccessible, or non-regular files with the least destructive behavior possible.

### Verification

Run:

```powershell
python -m unittest discover -s tests -v
```

### Commands

```powershell
python -m bounty_tools duplicate C:\Users\ALI\Documents
python -m bounty_tools duplicate C:\Users\ALI\Documents --min-size 1048576
python -m bounty_tools duplicate C:\Users\ALI\Documents --format json --output duplicates.json
python -m bounty_tools duplicate C:\Users\ALI\Documents --format csv --output duplicates.csv
```

## Human steps required

1. Review the deliverable and choose a bounty or freelance listing with a clear scope.
2. Log into the account and complete any CAPTCHA or identity check.
3. Submit the repository/worktree or a link to the relevant files.
4. Agree the price and delivery deadline.
5. Approve final scope and payment routing to:
   `0xc273959855147f5f537c80433c42f18335ec3bF1`
6. After platform payout is confirmed, verify receipt with a read-only balance check only.

## 2026-11-24 — JSON and market automation

### Built

Added `bounty_tools json-check` for validating JSON API responses, exported data, and JSON Lines logs:

- Validates one JSON document or one JSON value per non-empty JSONL line.
- Reports syntax errors with line and column.
- Continues through JSONL errors while limiting printed details with `--max-errors`.
- Reads either a file or stdin (`-`); uses only the Python standard library.
- Exit codes: `0` valid, `1` invalid JSON data, `2` input/encoding error.

### Usage

```powershell
python -m bounty_tools json-check response.json
python -m bounty_tools json-check events.jsonl --jsonl
Get-Content events.jsonl | python -m bounty_tools json-check - --jsonl
```

### Market scan

Re-ran `scan_markets.py` against its public aggregate feed. The feed contained 46 records: 0 met the explicit funded/open filters; 4 positive-reward leads were excluded because escrow was not confirmed. Details are in `OPPORTUNITIES.md`. The scan is read-only and requires no GitHub token.

### Verification

```powershell
python -m py_compile bounty_tools\jsoncheck.py bounty_tools\cli.py
python -m unittest discover -s tests -v
python scan_markets.py --output OPPORTUNITIES.md
```

Result: **20 tests passed**; market scan completed successfully.

### Packaging for small paid tasks

The CLI/JSON validation work can be offered as a fixed-scope automation deliverable: validate API payloads or JSONL logs in a CI step, add clear line-level diagnostics, and include a runnable command, sample input, acceptance checks, and tests. The same workflow adapts quickly to JSON import/export fixes, API integration bugs, and log-processing tasks. Agree scope and payment before starting a client-specific change.

### JSON edge-case follow-up

Added coverage and README guidance for empty JSON (invalid), empty JSONL (valid empty stream), mixed valid/invalid JSONL with line numbers, and invalid UTF-8 (input error / exit `2`). The stdin pipeline example now demonstrates a validation gate suitable for a PowerShell task or CI script.

Verification after this follow-up: **24 unit tests passed**, Python compilation succeeded, and the PowerShell stdin pipeline returned a valid JSONL result.

### Reusable delivery brief

Added `DELIVERABLES.md` as a reusable scope-and-handoff template for fixed-scope automation tasks. It captures inputs, expected behavior, exclusions, payment terms, deliverables, acceptance checks, test evidence, and the receiving-only EVM address. It also makes clear that platform account actions and final submission remain with the account holder.

### Sample task specification — split invalid JSONL records

Structured using `DELIVERABLES.md`; this is a proposed scope, not an implementation or a confirmed paid engagement.

- **Task:** Build a small CLI that validates a JSONL log stream and separates valid records from invalid lines.
- **Inputs:** One UTF-8 JSONL file or stdin, with an output directory. Each non-blank line is expected to contain one JSON value.
- **In scope:** Validate records independently; write valid JSON values as JSONL to `valid.jsonl`; write rejected records as JSONL objects to `invalid.jsonl`, including the 1-based source line number, original raw line, and parse diagnostic; print counts of valid, invalid, and skipped blank lines. Do not modify the source.
- **Out of scope:** Fetching logs from remote APIs, transforming valid records, deleting or overwriting the input, uploading results, wallet transactions, and platform account or bounty submission actions.
- **Acceptance criteria:**
  1. Valid records appear in `valid.jsonl` and rejected non-blank lines appear in `invalid.jsonl`.
  2. Invalid records include their original line number, raw content, and actionable error detail.
  3. Processing continues after a malformed JSON line; blank lines are skipped and counted.
  4. A fully valid stream exits successfully; a stream with rejected records exits nonzero and reports summary counts.
  5. Invalid UTF-8 is reported as an input error; the source remains unchanged.
- **Test expectations:** Cover all-valid input, mixed valid/invalid records with correct line numbers, blank-line counting, empty input, invalid UTF-8, output content and exit statuses. Use temporary files/directories and stdin tests; no network access or credentials.
- **Payment / EVM payout:** Agree amount, token, network, milestone, and platform conditions in writing before starting. Receiving address: `0xc273959855147f5f537c80433c42f18335ec3bF1`. Use it only to receive the agreed payment or for a read-only balance check after payout confirmation; never request or store private keys or seed phrases.

### JSONL valid/invalid output support

Added `separate_jsonl()` to share the validator's parsing behavior while streaming accepted lines unchanged and rejected lines as diagnostic JSONL objects (`line`, `column`, `reason`, and `raw`). Added paired `--valid-out` / `--invalid-out` options, limited to JSONL and protected against output path collisions; default CLI behavior is unchanged.

Verification: `python -m unittest discover -s tests -v` passed **29 tests** (the prior 24 plus 5 focused partition/CLI tests).
