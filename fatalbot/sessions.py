"""Thread-safe in-memory game session management."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .config import settings


class SessionError(Exception):
    pass


class RoundFinished(SessionError):
    pass


class SessionBusy(SessionError):
    pass


@dataclass
class GameSession:
    history: list[BaseMessage] = field(default_factory=list)
    attempts: int = 0
    won: bool = False
    finished: bool = False
    busy: bool = False


@dataclass(frozen=True)
class Attempt:
    session_id: str
    session: GameSession
    number: int
    history: list[BaseMessage]


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def create(self) -> tuple[str, GameSession]:
        session_id = secrets.token_urlsafe(24)
        session = GameSession()
        with self._lock:
            self._sessions[session_id] = session
        return session_id, session

    def get_or_create(self, session_id: str | None) -> tuple[str, GameSession]:
        if session_id:
            with self._lock:
                session = self._sessions.get(session_id)
            if session is not None:
                return session_id, session
        return self.create()

    def start_attempt(self, session_id: str | None) -> Attempt:
        resolved_id, session = self.get_or_create(session_id)
        with self._lock:
            if session.finished:
                raise RoundFinished("This player's round is over")
            if session.busy:
                raise SessionBusy("A reply is already being generated")
            session.busy = True
            session.attempts += 1
            return Attempt(
                session_id=resolved_id,
                session=session,
                number=session.attempts,
                history=list(session.history[-settings.max_history_messages :]),
            )

    def complete_attempt(self, attempt: Attempt, message: str, reply: str) -> bool:
        won = settings.flag in reply
        with self._lock:
            attempt.session.history.extend([HumanMessage(message), AIMessage(reply)])
            attempt.session.won = won
            attempt.session.finished = won or attempt.number >= settings.max_attempts
            attempt.session.busy = False
        return won

    def fail_attempt(self, attempt: Attempt) -> None:
        with self._lock:
            attempt.session.busy = False
            attempt.session.attempts = max(0, attempt.session.attempts - 1)

session_store = SessionStore()
