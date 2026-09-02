import json
import unittest

from fatalbot import api
from fatalbot.config import settings
from fatalbot.schemas import ChatRequest
from fatalbot.sessions import SessionStore


async def response_events(response) -> list[dict]:
    body = ""
    async for chunk in response.body_iterator:
        body += chunk.decode() if isinstance(chunk, bytes) else chunk
    return [json.loads(line) for line in body.splitlines()]


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_store = api.session_store
        self.original_stream = api.stream_reply
        api.session_store = SessionStore()

    async def asyncTearDown(self) -> None:
        api.session_store = self.original_store
        api.stream_reply = self.original_stream

    async def test_tokens_arrive_before_server_success_result(self) -> None:
        async def fake_stream(*_args):
            yield "Flag: "
            yield settings.flag

        api.stream_reply = fake_stream
        session_id, _ = api.session_store.create()
        response = await api.chat(ChatRequest(message="test", sessionId=session_id))
        events = await response_events(response)

        self.assertEqual(
            [event["type"] for event in events],
            ["start", "token", "token", "done"],
        )
        self.assertTrue(events[-1]["won"])
        self.assertTrue(events[-1]["roundOver"])
        self.assertEqual(events[-1]["flag"], settings.flag)


if __name__ == "__main__":
    unittest.main()
