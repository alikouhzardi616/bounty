import unittest

from find_bounties import confirmed_reward_text


class FundedBountyFilterTests(unittest.TestCase):
    def test_rejects_unfunded_issue(self) -> None:
        issue = {
            "title": "Fix the parser",
            "body": "This bounty is unfunded and bounty-waiting.",
        }
        self.assertIsNone(confirmed_reward_text(issue, []))

    def test_rejects_zero_reward(self) -> None:
        issue = {
            "title": "Small task",
            "body": "Funded bounty: $0",
        }
        self.assertIsNone(confirmed_reward_text(issue, []))

    def test_accepts_positive_explicit_reward(self) -> None:
        issue = {
            "title": "Fix CLI bug",
            "body": "Confirmed funded reward: $250 USDC.",
        }
        reward = confirmed_reward_text(issue, [])
        self.assertIsNotNone(reward)
        self.assertIn("250", reward)


if __name__ == "__main__":
    unittest.main()
