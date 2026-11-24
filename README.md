# Duplicate File Reporter

A dependency-free Python CLI that scans a directory and reports identical files. It is useful for disk cleanup audits, repository hygiene checks, migration reviews, and client data cleanup.

The tool never deletes or modifies files.

## Run

```powershell
python -m bounty_tools duplicate C:\Users\ALI\Documents
```

Filter small files:

```powershell
python -m bounty_tools duplicate C:\Users\ALI\Documents --min-size 1048576
```

Write JSON:

```powershell
python -m bounty_tools duplicate C:\Users\ALI\Documents --format json --output duplicates.json
```

Write CSV:

```powershell
python -m bounty_tools duplicate C:\Users\ALI\Documents --format csv --output duplicates.csv
```

## Behavior

- Recursively scans regular files.
- Ignores files smaller than `--min-size`.
- Uses size prechecks and SHA-256 hashing.
- Preserves path spelling and sorts results consistently.
- Outputs a human-readable table by default.
- Exits with status `0` when finished successfully; invalid paths are reported as errors.

## Scan crypto bounty feeds

Use the read-only market scanner to check the published Bounty Radar JSON feed, which aggregates bounty sources and includes escrow and competing-PR metadata:

```powershell
python scan_markets.py --output OPPORTUNITIES.md
```

Only tasks with a positive reward, fresh open status, explicit funded/escrowed evidence, and no known competing pull request are shown as actionable. Other positive-reward listings remain marked as unverified leads; no account or wallet connection is required to scan.

## Validate JSON and JSON Lines

Check a JSON document:

```powershell
python -m bounty_tools json-check response.json
```

Check newline-delimited JSON from a log or API stream:

```powershell
python -m bounty_tools json-check events.jsonl --jsonl
Get-Content .\api-response.json -Raw | python -m bounty_tools json-check -
Get-Content .\events.jsonl | python -m bounty_tools json-check - --jsonl --max-errors 5
if ($LASTEXITCODE -ne 0) { throw "Input validation failed" }
```

JSONL mode skips blank lines (an empty JSONL stream is valid), reports line and column for invalid records, and limits printed error details with `--max-errors`. An empty regular JSON document is invalid; non-UTF-8 files return exit code `2`.

To split a JSONL stream into accepted records and rejected records with diagnostics:

```powershell
python -m bounty_tools json-check events.jsonl --jsonl `
  --valid-out valid.jsonl --invalid-out invalid.jsonl
```

`valid.jsonl` contains the valid input lines. Each line in `invalid.jsonl` is a JSON object with the source `line`, error `column`, parser `reason`, and original `raw` line. The two output options must be used together with `--jsonl`; they must be different from each other and from the input. The command keeps its existing stdout/stderr and exit-code behavior.
