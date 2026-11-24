# Scoped Automation Deliverable

Use this brief to agree a small, testable automation task before implementation. Replace bracketed fields for each client or bounty; confirm the scope, acceptance criteria, deadline, and payment terms in writing first.

## Task brief

- **Task:** [Short description of the specific problem]
- **Inputs:** [Sample files, API endpoint/schema, operating system, and constraints]
- **Expected result:** [Exact output, behavior, or workflow improvement]
- **Out of scope:** [Explicit exclusions and assumptions]
- **Deadline:** [Agreed date and time]
- **Payment:** [Agreed amount, currency/token, network, and payment milestone]

## Delivery contents

- Focused source code and a runnable command or integration example.
- Tests covering the agreed behavior and relevant failure cases.
- Short usage documentation with sample input and expected output.
- A completion note listing changed files, test command, and test result.

## Acceptance criteria

1. The agreed input produces the expected output.
2. Invalid or unavailable input produces an actionable error and a non-success status.
3. Automated tests pass using the documented command.
4. No credentials, private keys, or seed phrases are required or included.
5. Any additional request outside the agreed scope is estimated and approved separately.

## Verification

For this workspace's Python tools:

```powershell
python -m unittest discover -s tests -v
```

For a client-specific task, add the agreed focused test command and record its actual result in the completion note.

## Receiving payment

Use this public EVM address only for receiving agreed payouts:

`0xc273959855147f5f537c80433c42f18335ec3bF1`

Confirm the supported network, asset, amount, and payout conditions with the client or platform before starting. Never share or request a private key or seed phrase. Account login, identity checks, and final submission remain actions for the account holder.
## Task Deliverable: JSONL Log Validation & Bad-Record Separation

- **Summary:** A CLI utility that validates a JSONL file or stdin and separates valid records from invalid records with line/column diagnostics.
- **Inputs & In-Scope:**
  - UTF-8 JSONL input from a file path or stdin (`-`); blank lines are skipped, and an empty stream is valid.
  - Both `--valid-out` and `--invalid-out` must be supplied with `--jsonl`. The paths must differ from each other and from the input.
  - Valid records are written as JSONL to the valid output. Each invalid-output line is a JSON object containing `line`, `column`, `reason`, and the original `raw` line.
  - Exit codes: `0` when all checked records are valid, `1` when JSONL records are invalid, and `2` for input, encoding, or output errors.
- **Out of Scope:**
  - Transforming or enriching fields inside valid records.
  - Silent auto-repair or guessing of malformed records without error reporting.
  - Modifying the source file, remote fetching/uploading, external database/message queue/cloud integrations, and server deployment.
- **Acceptance Criteria:**
  - Valid JSONL lines and invalid JSONL lines are separated accurately; processing continues after individual malformed records.
  - Every invalid record includes its source line, parser column, original raw line, and error reason.
  - Empty streams produce empty output files and a successful result; invalid UTF-8 is reported as an input error.
  - The default `json-check` behavior and existing validation diagnostics remain unchanged when output options are omitted.
- **Verification & Artifacts:**
  - Test command: `python -m unittest discover -s tests -v`.
  - Tests cover valid, mixed, and empty streams, structured diagnostics, CLI output options, and existing default behavior. The current suite has **29 passing tests**.
  - Deliver the updated code, tests, concise usage notes, and test result.
- **Payout Terms:**
  - Agree the fixed price, token, network, and payout conditions before starting. Use EVM address `0xc273959855147f5f537c80433c42f18335ec3bF1` only to receive payment or for a read-only balance check after payout confirmation. No signing, private keys, or recovery phrases.