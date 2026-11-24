from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


GITHUB_API = "https://api.github.com/"
USER_AGENT = "bounty-automation/1.0"
DEFAULT_OUTPUT = Path("OPPORTUNITIES.md")

BASIC_QUERIES = (
    'is:issue is:open "Algora" bounty',
    'is:issue is:open "Polar" bounty',
    'is:issue is:open "Opire" bounty',
    'is:issue is:open "funded bounty" in:title,body',
    'is:issue is:open "bounty: $" in:title,body',
    'is:issue is:open "reward: $" in:title,body',
)

COMPLEX_LABELS = {
    "epic",
    "feature",
    "breaking-change",
    "roadmap",
    "research",
    "needs discussion",
}

EXCLUDED_LABELS = {
    "bounty-waiting",
    "unfunded",
    "funding",
    "not funded",
    "reward awaiting",
    "bounty pending",
    "status:review",
    "season-0",
    "bounty-alert",
}

FUNDED_BOT_NAMES = (
    "algora",
    "polar",
    "opire",
)

REWARD_PATTERN = re.compile(
    r"(?:\$|€|£)\s*\d[\d,.]*"
    r"|(?:\d[\d,.]*\s*(?:usd|usdc|nim|eth|sol|btc)\b)"
    r"|(?:bounty|reward)\s*(?:of\s*)?(?:is\s*)?\s*\d[\d,.]*",
    re.IGNORECASE,
)


def github_get(path: str, token: str | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(GITHUB_API + path, headers=headers)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, http.client.IncompleteRead) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 403:
                raise
            if attempt < 2:
                time.sleep(1 + attempt)
    raise last_error or RuntimeError("GitHub request failed")


def search_issues(query: str, token: str | None = None) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": "50",
        }
    )
    payload = github_get("search/issues?" + params, token)
    return payload.get("items", [])


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def repo_coordinates(issue: dict) -> tuple[str, str] | None:
    repo_url = str(issue.get("repository_url", ""))
    marker = "/repos/"
    if marker not in repo_url:
        return None
    coordinates = repo_url.split(marker, 1)[1].strip("/")
    parts = coordinates.split("/")
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def issue_comments(issue: dict, token: str | None) -> list[dict]:
    coordinates = repo_coordinates(issue)
    if not coordinates:
        return []
    owner, repo = coordinates
    path = f"repos/{owner}/{repo}/issues/{issue['number']}/comments?per_page=100"
    try:
        payload = github_get(path, token)
    except (urllib.error.HTTPError, urllib.error.URLError, http.client.IncompleteRead):
        return []
    return payload if isinstance(payload, list) else []


def has_open_competing_pr(issue: dict, token: str | None) -> bool | None:
    coordinates = repo_coordinates(issue)
    if not coordinates:
        return None
    owner, repo = coordinates
    number = int(issue["number"])
    query = f'repo:{owner}/{repo} is:pr is:open "{number}"'
    params = urllib.parse.urlencode({"q": query, "per_page": "20"})
    try:
        payload = github_get("search/issues?" + params, token)
    except (urllib.error.HTTPError, urllib.error.URLError, http.client.IncompleteRead):
        return None
    if payload.get("total_count", 0) > 0:
        return True
    return False


def confirmed_reward_text(issue: dict, comments: list[dict]) -> str | None:
    text = "\n".join(
        [
            str(issue.get("title", "")),
            str(issue.get("body") or ""),
            *[str(comment.get("body") or "") for comment in comments],
        ]
    )
    lower = text.lower()

    if any(
        blocked in lower
        for blocked in (
            "manual pull requests",
            "manual prs",
            "pull requests are not reviewed",
            "automated ci regression mirror",
            "has no real value",
            "test eth",
            "pilot is paused",
            "do not create or fund",
            "not offering an open",
            "one selected participant",
            "hackathon",
            "bounty: $",
            "bounty alert",
            "new opportunities",
            "minimum",
            "upfront deposit",
            "seller submission",
            "penniless",
            "first £",
            "bounty=0",
            "bounty mechanism",
            "bounty is expired",
            "algora bounty is expired",
            "no longer available",
        )
    ):
        return None

    if any(
        blocked in lower
        for blocked in (
            "bounty-waiting",
            "unfunded",
            "not funded",
            "awaiting funding",
            "funding pending",
        )
    ):
        return None

    bot_confirmed = any(
        re.search(rf"\b{re.escape(bot)}\b", lower)
        for bot in FUNDED_BOT_NAMES
    )
    amount_match = REWARD_PATTERN.search(text)
    if amount_match:
        reward_numbers = re.findall(r"\d[\d,.]*", amount_match.group(0))
        if reward_numbers:
            try:
                if float(reward_numbers[0].replace(",", "")) <= 0:
                    return None
            except ValueError:
                return None

    confirmed_phrases = (
        "funded",
        "confirmed",
        "active bounty",
        "bounty posted",
        "reward available",
        "paid",
    )
    if bot_confirmed and any(phrase in lower for phrase in confirmed_phrases):
        return amount_match.group(0).strip() if amount_match else None
    if amount_match and any(phrase in lower for phrase in confirmed_phrases):
        return amount_match.group(0).strip()
    return None


def score_issue(
    issue: dict,
    max_stale_days: int,
    token: str | None,
) -> tuple[int, list[str], str] | None:
    state = issue.get("state")
    if state != "open":
        return None

    updated = parse_time(issue["updated_at"])
    age_days = (datetime.now(timezone.utc) - updated).days
    if age_days > max_stale_days:
        return None

    labels = {
        str(label.get("name", "")).strip().lower()
        for label in issue.get("labels", [])
        if isinstance(label, dict)
    }
    if labels & COMPLEX_LABELS or labels & EXCLUDED_LABELS:
        return None

    reward = confirmed_reward_text(issue, [])
    if not reward:
        comments = issue_comments(issue, token)
        reward = confirmed_reward_text(issue, comments)
    if not reward:
        return None

    competing_pr = has_open_competing_pr(issue, token)
    if competing_pr is not False:
        return None

    title = str(issue.get("title", ""))
    body = str(issue.get("body") or "")
    text = f"{title}\n{body}".lower()

    score = 0
    reasons: list[str] = []
    for keyword in ("bounty", "reward", "paid", "prize"):
        if keyword in text:
            score += 20
            reasons.append(keyword)
            break

    for keyword in ("amount", "payout", "usd", "usdc", "dollars"):
        if keyword in text:
            score += 10
            break

    for keyword in ("good first issue", "easy", "small", "quick", "micro"):
        if keyword in text or keyword in labels:
            score += 15
            reasons.append("small-scope signal")
            break

    if labels & {"help wanted", "good first issue", "bug", "automation", "cli"}:
        score += 10

    if issue.get("comments", 0) <= 5:
        score += 10
    if not issue.get("assignee"):
        score += 5
    if age_days <= 14:
        score += 15
    elif age_days <= 30:
        score += 8

    title_lower = title.lower()
    if any(word in title_lower for word in ("refactor", "rewrite", "migrate")):
        score -= 20
    if any(word in title_lower for word in ("implement full", "complete redesign")):
        score -= 25

    if score < 25:
        return None
    reasons.append(f"confirmed reward: {reward}")
    return score, reasons, reward


def collect_matches(
    max_stale_days: int,
    token: str | None,
    limit: int,
) -> list[dict]:
    matches: dict[int, dict] = {}
    for query in BASIC_QUERIES:
        try:
            items = search_issues(query, token)
        except urllib.error.HTTPError as exc:
            print(
                f"GitHub API warning for query {query!r}: HTTP {exc.code}",
                file=sys.stderr,
            )
            continue
        except urllib.error.URLError as exc:
            print(
                f"GitHub API warning for query {query!r}: {exc.reason}",
                file=sys.stderr,
            )
            continue
        except http.client.IncompleteRead as exc:
            print(
                f"GitHub API warning for query {query!r}: incomplete response",
                file=sys.stderr,
            )
            continue

        for issue in items:
            scored = score_issue(issue, max_stale_days, token)
            if not scored:
                continue
            score, reasons, reward = scored
            prior = matches.get(issue["id"])
            if prior is None or score > prior["_score"]:
                issue["_score"] = score
                issue["_reasons"] = reasons
                issue["_reward"] = reward
                matches[issue["id"]] = issue
        time.sleep(0.25)

    ranked = sorted(
        matches.values(),
        key=lambda issue: (
            -int(issue["_score"]),
            parse_time(issue["updated_at"]),
        ),
        reverse=False,
    )
    ranked.sort(key=lambda issue: int(issue["_score"]), reverse=True)
    return ranked[:limit]


def escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(matches: Iterable[dict]) -> str:
    match_list = list(matches)
    lines = [
        "# Public Bounty Opportunities",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Source: public GitHub Issues Search API.",
        "This is a lead list only; no account action or submission was attempted.",
        "",
    ]

    if not match_list:
        lines.extend(
            [
                "## No actionable matches",
                "",
                "The public search returned no issue meeting the stale, complexity, and scope filters.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "| Score | Reward | Repository | Issue | Updated | Comments | Labels |",
            "|---:|---|---|---|---|---:|---|",
        ]
    )
    for issue in match_list:
        repo_url = issue["repository_url"]
        repo = repo_url.rsplit("/", 1)[-1]
        labels = ", ".join(
            escape(label["name"])
            for label in issue.get("labels", [])
            if isinstance(label, dict)
        )
        lines.append(
            "| {score} | {reward} | [{repo}]({repo_url}) "
            "| [#{number} {title}]({html_url}) "
            "| {updated} | {comments} | {labels} |".format(
                score=issue["_score"],
                reward=escape(issue["_reward"]),
                repo=escape(repo),
                repo_url=escape(repo_url.replace("api.github.com/repos", "github.com")),
                number=issue["number"],
                title=escape(issue["title"]),
                html_url=escape(issue["html_url"]),
                updated=issue["updated_at"][:10],
                comments=issue["comments"],
                labels=labels or "-",
            )
        )

    best = match_list[0]
    lines.extend(
        [
            "",
            "## Recommended first candidate",
            "",
            f"- **Issue:** [{escape(best['title'])}]({escape(best['html_url'])})",
            f"- **Score:** {best['_score']}",
            f"- **Confirmed reward:** {escape(best['_reward'])}",
            f"- **Open and no competing PR detected:** Yes",
            f"- **Why:** {', '.join(best['_reasons']) or 'basic scoring match'}",
            f"- **Next local step:** Open the issue and repository in read-only mode, verify the acceptance criteria, and clone only after confirming the license and scope.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find fast, public GitHub bounty leads.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=60,
        help="Maximum number of days since the issue was updated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Maximum number of opportunities to write.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output Markdown file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_stale_days < 1:
        print("Error: --max-stale-days must be at least 1", file=sys.stderr)
        return 2
    if args.limit < 1:
        print("Error: --limit must be at least 1", file=sys.stderr)
        return 2

    import os

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    matches = collect_matches(args.max_stale_days, token, args.limit)
    args.output.write_text(
        render_markdown(matches),
        encoding="utf-8",
    )
    print(f"Wrote {len(matches)} actionable match(es) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
