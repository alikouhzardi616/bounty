# Human Action Required

No human action is required to search public GitHub issues or prepare local work.

The automation stops and creates no submission or claim until one of these actions is reached:

1. GitHub account login if a private operation is needed.
2. A two-factor authentication or CAPTCHA challenge.
3. Repository forking or branch creation.
4. Pull request submission or issue comment submission.
5. Bounty platform login or payout claim.
6. Payment acceptance or payout-address confirmation.

## Receiving wallet

`0xc273959855147f5f537c80433c42f18335ec3bF1`

Use only for receiving payouts or read-only balance checks.

## Strict bounty selection result

No current funded candidate passed the strict human-actionable filters.

Rejected during the latest review:

- RustDesk #3762: the Algora bounty was reported expired.
- VAN community #2: the external pilot was paused and no work should start.
- Mergit #8: the ETH reward is explicitly free test ETH with no real value.
- Agent conformance quarantine #2: manual PRs are not reviewed on the automated mirror.
- Escrow/bounty alerts, duplicate bounties, one-time selection tasks, test-only pilots, expired opportunities, and bounty mechanisms paying zero were excluded.

## Next human action

## Account setup priority

No funded task currently needs claiming. The current feed had four positive-reward leads, but none had confirmed escrow. Create accounts only when ready to apply; never share passwords, API keys, signatures, or wallet recovery material in this workspace.

1. **GitHub — required baseline**
   - Sign in at https://github.com/
   - Ensure the contributor profile is public enough to review, enable MFA, and keep a clean email/profile.
   - Use it for issue discussion, repositories, and pull requests. A GitHub account alone does not confirm a payout.

2. **Dework — best candidate for a Web3 contributor profile**
   - Open https://app.dework.xyz/grants and browse open bounties before connecting.
   - Create/sign in to a contributor profile, add relevant skills, and follow DAOs whose tasks match.
   - Connect GitHub only where the task/community asks for it.
   - Connect the EVM wallet from the user's wallet app. Dework's published payment guide lists Ethereum, Gnosis, Polygon, Arbitrum, Optimism and other networks; confirm the selected task's payout chain/token before applying.
   - Never sign a transaction or spend funds merely to browse or apply.

3. **Opire — conditional; do not connect yet**
   - Public site requests failed with DNS/transport errors during this scan, and the aggregator flags Opire availability as unreliable.
   - Wait until https://opire.dev loads normally, verify current payout and claim terms, then create/connect an account only if the task explicitly supports the desired EVM network.

**Not recommended for bounty signup right now:** Algora's official current `llms.txt` describes a technical recruiting/hiring platform; its prior open-source bounty flow is not confirmed as currently operating.

## Scanner command

Run the public, read-only multi-source scanner:

```powershell
python scan_markets.py --output OPPORTUNITIES.md
```

The scanner consumes the public Bounty Radar JSON feed, which aggregates sources. It rejects entries without explicit escrow/funding confirmation, a positive reward, freshness, and known zero competing PRs for GitHub issues. No login or token is needed for this scanner.
