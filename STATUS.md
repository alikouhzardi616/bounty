# STATUS

- Sprint: **Active**
- Capital: **$0 starting capital**
- Primary focus: **Reusable automation and quick bug fixes**
- Delivery standard: **Working code, focused tests, concise README, clean evidence**
- Verification target: **Tests pass locally before delivery**

## Receiving wallet

`0xc273959855147f5f537c80433c42f18335ec3bF1`

## Capability boundary

The AI worker can build, test, package, and document paid-work deliverables inside `bounty`. External login, CAPTCHA completion, bounty claiming, bid submission, and payout acceptance require the user's account and approval.

## Automation loop

- **A - Search:** public GitHub issue endpoints
- **B - Select and prepare:** score realistic open issues, analyze locally, implement and test where practical
- **C - Human handoff:** record exact account/login/submission steps in `HUMAN_NEEDED.md`
- **No silent claiming:** the loop stops before account actions or irreversible submissions

## Latest market scan — 2026-11-25

- Latest scan: 2026-11-24 20:44 UTC; public Bounty Radar feed reported generation at 2026-11-24 16:34 UTC; **46 records**
- Verified positive-reward tasks with explicit locked escrow and no competing PRs: **0**
- Positive-reward leads excluded because locked escrow is unverified: **4**
- Scanner command: `python scan_markets.py --output OPPORTUNITIES.md`
- No credentials, account access, wallet signing, or claims were used.

## Ready-to-reuse local utility

- `python -m bounty_tools json-check <file>` validates a JSON document.
- Add `--jsonl` to validate newline-delimited JSON, including stdin with `-`.
- Edge coverage: empty JSON, empty JSONL, mixed-validity JSONL, and invalid UTF-8.
- Latest verification: **24 unit tests passed**; PowerShell stdin example passed.
