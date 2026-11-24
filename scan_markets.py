from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "bounty-market-scanner/1.0 (public read-only; contact: local workspace)"
DEFAULT_OUTPUT = Path("OPPORTUNITIES.md")
TIMEOUT_SECONDS = 20
REQUEST_DELAY_SECONDS = 0.5


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    format: str


# Public static JSON feed; it aggregates multiple sources and includes escrow
# and competing-PR metadata. Unknown escrow is never treated as funded.
FEEDS = (
    Feed(
        name="Bounty Radar (aggregated feed)",
        url="https://muhib-karim.github.io/bounty-radar/bounties.json",
        format="bounty-radar",
    ),
)

AMOUNT_RE = re.compile(r"(?:\$\s?\d[\d,.]*|\d[\d,.]*\s?(?:USDC|USDT|DAI|ETH|WETH|MATIC|OP|ARB|NIM|USD))", re.I)
STALE_DAYS = 45
MAX_FEED_AGE_HOURS = 24


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise ValueError(f"Expected JSON response, got {content_type or 'unknown'}")
        return json.loads(response.read().decode("utf-8"))


def walk_records(value: Any):
    if isinstance(value, dict):
        if any(key in value for key in ("title", "name")) and any(
            key in value for key in ("url", "html_url", "amount", "reward", "bounty")
        ):
            yield value
        for nested in value.values():
            yield from walk_records(nested)
    elif isinstance(value, list):
        for item in value:
            yield from walk_records(item)


def get_text(record: dict) -> str:
    fields = ("title", "name", "description", "body", "url", "html_url", "repository")
    return " ".join(str(record.get(field) or "") for field in fields)


def get_state(record: dict) -> str:
    for key in ("status", "state", "bounty_status", "funding_status"):
        value = record.get(key)
        if value is not None:
            return str(value).strip().lower()
    return ""


def get_amount(record: dict) -> tuple[str, float] | None:
    for key in ("reward", "amount", "amountUsd", "bounty", "prize", "value"):
        value = record.get(key)
        if isinstance(value, dict):
            quantity = value.get("amount") or value.get("value")
            currency = value.get("currency") or value.get("token") or value.get("symbol")
            if quantity is not None and currency:
                try:
                    number = float(str(quantity).replace(",", ""))
                except ValueError:
                    continue
                if number > 0:
                    return f"{quantity} {currency}", number
        elif isinstance(value, (int, float)) and value > 0:
            currency = "USD" if key == "amountUsd" else (
                record.get("currency") or record.get("token") or record.get("symbol") or "USD"
            )
            return f"{value:g} {currency}", float(value)
        elif isinstance(value, str):
            match = AMOUNT_RE.search(value)
            if match:
                amount_text = match.group(0).strip()
                number_match = re.search(r"\d[\d,.]*", amount_text)
                if number_match:
                    try:
                        number = float(number_match.group(0).replace(",", ""))
                    except ValueError:
                        continue
                    if number > 0:
                        return amount_text, number
    text = get_text(record)
    match = AMOUNT_RE.search(text)
    if match:
        amount_text = match.group(0).strip()
        number_match = re.search(r"\d[\d,.]*", amount_text)
        if number_match:
            try:
                number = float(number_match.group(0).replace(",", ""))
            except ValueError:
                return None
            if number > 0:
                return amount_text, number
    return None


def is_confirmed_funded(record: dict) -> bool:
    state = get_state(record)
    if state in {"funded", "escrowed", "payment_secured"}:
        return True
    for key in ("funded", "is_funded", "escrowed", "is_escrowed"):
        if record.get(key) is True:
            return True
    escrow = str(record.get("escrow") or "").strip().lower()
    if not escrow:
        return False
    unknown_markers = ("unknown", "verify", "unverified", "not funded", "pending")
    if any(marker in escrow for marker in unknown_markers):
        return False
    return any(marker in escrow for marker in ("funded", "escrowed", "secured"))


def is_open(record: dict) -> bool:
    state = get_state(record)
    if state in {"closed", "complete", "completed", "paid", "expired", "cancelled", "canceled", "claimed", "in_progress", "in progress"}:
        return False
    for key in ("closed", "completed", "claimed", "expired", "cancelled", "canceled"):
        if record.get(key) is True:
            return False
    if "issue" in record:
        if "openCompetingPrs" not in record or record["openCompetingPrs"] is None:
            return False
        try:
            if int(record["openCompetingPrs"]) > 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def record_url(record: dict) -> str:
    for key in ("html_url", "url", "web_url", "link"):
        value = record.get(key)
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return ""


def record_updated(record: dict) -> datetime | None:
    for key in ("updated_at", "updatedAt", "created_at", "createdAt", "last_seen"):
        value = record.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def feed_age_hours(payload: dict) -> float | None:
    value = payload.get("generatedAt") or payload.get("generated_at")
    if not isinstance(value, str):
        return None
    try:
        generated = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - generated).total_seconds() / 3600)


def normalize_record(feed_name: str, record: dict) -> dict | None:
    title = str(record.get("title") or record.get("name") or "").strip()
    url = record_url(record)
    reward = get_amount(record)
    if not title or not url or not reward or not is_open(record) or not is_confirmed_funded(record):
        return None

    if record.get("ageDays") is not None:
        try:
            age_days = max(0, int(record["ageDays"]))
        except (TypeError, ValueError):
            return None
        if age_days > STALE_DAYS:
            return None
        updated = record_updated(record)
    else:
        updated = record_updated(record)
        age_days = None
    if updated:
        timestamp_age = max(0, (datetime.now(timezone.utc) - updated).days)
        if timestamp_age > STALE_DAYS:
            return None
        if age_days is None:
            age_days = timestamp_age

    amount, numeric_amount = reward
    description = re.sub(r"\s+", " ", str(record.get("description") or record.get("body") or "")).strip()
    if len(description) > 400:
        description = description[:397] + "..."
    return {
        "source": feed_name,
        "title": title,
        "url": url,
        "reward": amount,
        "reward_value": numeric_amount,
        "description": description,
        "age_days": age_days,
        "updated": updated.isoformat() if updated else "unknown",
        "status": get_state(record) or "open",
        "raw": record,
    }


def fetch_feed(feed: Feed) -> tuple[list[dict], list[dict], int]:
    payload = fetch_json(feed.url)
    if feed.format == "bounty-radar":
        if not isinstance(payload, dict) or not isinstance(payload.get("bounties"), list):
            raise ValueError("Unexpected Bounty Radar feed schema")
        age = feed_age_hours(payload)
        if age is None:
            raise ValueError("Feed has no valid generatedAt timestamp")
        if age > MAX_FEED_AGE_HOURS:
            raise ValueError(f"Feed is stale ({age:.1f} hours old)")
        payload = payload["bounties"]
    records = []
    seen = set()
    unverified_funding: list[dict] = []
    for record in walk_records(payload):
        if get_amount(record) and is_open(record) and not is_confirmed_funded(record):
            reward = get_amount(record)
            if reward:
                unverified_funding.append(
                    {
                        "title": str(record.get("title") or record.get("name") or "Untitled"),
                        "url": record_url(record),
                        "reward": reward[0],
                        "escrow": str(record.get("escrow") or "not stated"),
                        "source": str(record.get("source") or "aggregated source"),
                    }
                )
        normalized = normalize_record(feed.name, record)
        if normalized and normalized["url"] not in seen:
            seen.add(normalized["url"])
            records.append(normalized)
    return records, unverified_funding, len(payload) if isinstance(payload, list) else 0


def estimate_fastness(item: dict) -> int:
    text = f"{item['title']} {item['description']}".lower()
    score = 50
    quick_signals = ("docs", "documentation", "small", "typo", "test", "cli", "bug")
    complex_signals = ("rewrite", "protocol", "migration", "architecture", "security audit", "smart contract")
    score += 10 * sum(signal in text for signal in quick_signals)
    score -= 15 * sum(signal in text for signal in complex_signals)
    age = item.get("age_days")
    if age is not None:
        score += max(0, 15 - age)
    return max(0, min(100, score))


def render_markdown(
    items: list[dict],
    statuses: list[str],
    unverified_leads: list[dict],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Crypto-Friendly Bounty Opportunities",
        "",
        f"Scanned: {now}",
        "",
        "Data comes from a public third-party aggregator. Verify escrow and terms at the original platform before spending time.",
        "No accounts were accessed and no bounty was claimed or submitted.",
        "",
        "## Feed status",
        "",
    ]
    lines.extend(f"- {status}" for status in statuses)
    lines.append("")

    if not items:
        lines.extend(
            [
                "## No verified opportunities",
                "",
                "No configured public platform feed returned a task with both an explicit positive reward and confirmed funded/open status.",
                "",
            ]
        )
        if unverified_leads:
            lines.extend(
                [
                    "## Leads excluded: escrow not confirmed",
                    "",
                    "These are not actionable opportunities. Confirm funding and task availability directly before considering them.",
                    "",
                    "| Reward shown | Source | Task | Escrow metadata |",
                    "|---:|---|---|---|",
                ]
            )
            for lead in unverified_leads[:10]:
                lines.append(
                    f"| {escape_md(lead['reward'])} | {escape_md(lead['source'])} | "
                    f"[{escape_md(lead['title'])}]({lead['url']}) | "
                    f"{escape_md(lead['escrow'])} |"
                )
            lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "## Funded and open tasks (ranked by likely completion speed)",
            "",
            "| Rank | Speed | Platform | Reward | Status | Task | Updated |",
            "|---:|---:|---|---:|---|---|---|",
        ]
    )
    for rank, item in enumerate(items, start=1):
        lines.append(
            f"| {rank} | {item['speed_score']}/100 | {item['source']} | "
            f"{item['reward']} | {item['status']} | "
            f"[{escape_md(item['title'])}]({item['url']}) | "
            f"{item['age_days'] if item['age_days'] is not None else 'unknown'} days ago |"
        )
        if item["description"]:
            lines.append(f"\n**Details:** {escape_md(item['description'])}\n")
    lines.append("")
    return "\n".join(lines)


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan public crypto bounty and task feeds.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    all_items: list[dict] = []
    unverified_leads: list[dict] = []
    statuses = []
    successful_feeds = 0
    for index, feed in enumerate(FEEDS):
        if index:
            time.sleep(REQUEST_DELAY_SECONDS)
        try:
            found, unverified_funding, total = fetch_feed(feed)
            all_items.extend(found)
            unverified_leads.extend(unverified_funding)
            successful_feeds += 1
            statuses.append(
                f"{feed.name}: OK; {total} records, {len(found)} verified funded/open task(s), "
                f"{len(unverified_funding)} positive-reward open lead(s) without confirmed escrow."
            )
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            status = f"{feed.name}: unavailable ({exc})."
            print(status, file=sys.stderr)
            statuses.append(status)

    unique = {item["url"]: item for item in all_items}
    items = list(unique.values())
    for item in items:
        item["speed_score"] = estimate_fastness(item)
    items.sort(key=lambda item: (-item["speed_score"], item.get("age_days") or 10**6))

    args.output.write_text(
        render_markdown(items, statuses, unverified_leads),
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} verified opportunity/opportunities to {args.output}")
    return 0 if successful_feeds else 1


if __name__ == "__main__":
    raise SystemExit(main())
