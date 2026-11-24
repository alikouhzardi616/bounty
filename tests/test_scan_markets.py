import unittest

from scan_markets import (
    feed_age_hours,
    is_confirmed_funded,
    is_open,
    normalize_record,
)


class MarketFeedTests(unittest.TestCase):
    def test_unknown_escrow_is_not_funded(self) -> None:
        record = {
            "title": "Paid task",
            "url": "https://github.com/acme/tool/issues/1",
            "amountUsd": 100,
            "escrow": "unknown — verify escrow",
            "issue": 1,
            "openCompetingPrs": 0,
        }
        self.assertFalse(is_confirmed_funded(record))
        self.assertIsNone(normalize_record("feed", record))

    def test_explicit_escrowed_reward_is_eligible(self) -> None:
        record = {
            "title": "Small docs task",
            "url": "https://github.com/acme/tool/issues/1",
            "amountUsd": 100,
            "escrow": "Algora (escrowed)",
            "issue": 1,
            "openCompetingPrs": 0,
            "ageDays": 1,
        }
        item = normalize_record("feed", record)
        self.assertIsNotNone(item)
        self.assertEqual(item["reward"], "100 USD")

    def test_competing_pr_disqualifies_issue(self) -> None:
        self.assertFalse(
            is_open(
                {
                    "state": "open",
                    "issue": 1,
                    "openCompetingPrs": 2,
                }
            )
        )

    def test_unknown_competing_pr_count_is_not_actionable(self) -> None:
        self.assertFalse(is_open({"state": "open", "issue": 1}))

    def test_feed_generation_time_is_parsed(self) -> None:
        age = feed_age_hours({"generatedAt": "2026-11-24T16:34:56Z"})
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)


if __name__ == "__main__":
    unittest.main()
