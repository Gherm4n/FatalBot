"""Application configuration and club-content loading."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
CLUB_INFO_PATH = ROOT / "club_info.json"
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("FATALBOT_HOST", "127.0.0.1")
    port: int = int(os.getenv("FATALBOT_PORT", "8080"))
    model_name: str = os.getenv("MODEL_NAME", "qwen3.5")
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
    )
    flag: str = os.getenv("FATALBOT_FLAG", "FATAL{welcome_to_the_club}")
    max_history_messages: int = 12
    max_message_length: int = 2000
    max_attempts: int = 3


@dataclass(frozen=True)
class ClubInfo:
    name: str
    welcome: str
    facts: tuple[str, ...]


def load_club_info(path: Path = CLUB_INFO_PATH) -> ClubInfo:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    facts = data.get("facts")
    if not isinstance(facts, list) or not facts or not all(
        isinstance(fact, str) and fact.strip() for fact in facts
    ):
        raise ValueError("club_info.json must contain a non-empty 'facts' list")
    return ClubInfo(
        name=data.get("club_name", "Cybersecurity Club"),
        welcome=data.get("welcome", "Can you extract the flag?"),
        facts=tuple(facts),
    )


settings = Settings()
club_info = load_club_info()
