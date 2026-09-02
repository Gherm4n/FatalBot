import unittest

from fatalbot.config import settings
from fatalbot.sessions import RoundFinished, SessionStore


class SessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionStore()
        self.session_id, self.session = self.store.create()

    def test_history_is_available_to_later_attempts(self) -> None:
        first = self.store.start_attempt(self.session_id)
        self.store.complete_attempt(first, "first prompt", "first answer")
        second = self.store.start_attempt(self.session_id)
        self.assertEqual(
            [message.content for message in second.history],
            ["first prompt", "first answer"],
        )

    def test_three_failures_finish_the_round(self) -> None:
        for number in range(1, settings.max_attempts + 1):
            attempt = self.store.start_attempt(self.session_id)
            self.store.complete_attempt(attempt, f"prompt {number}", "no secret")
        self.assertTrue(self.session.finished)
        with self.assertRaises(RoundFinished):
            self.store.start_attempt(self.session_id)

    def test_winning_finishes_the_round(self) -> None:
        attempt = self.store.start_attempt(self.session_id)
        self.store.complete_attempt(attempt, "prompt", settings.flag)
        self.assertTrue(self.session.won)
        self.assertTrue(self.session.finished)


if __name__ == "__main__":
    unittest.main()
