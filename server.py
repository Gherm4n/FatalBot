#!/usr/bin/env python3
"""Development entry point for FatalBot."""

import uvicorn

from fatalbot.api import app
from fatalbot.config import settings


def main() -> None:
    print(f"FatalBot is running at http://{settings.host}:{settings.port}")
    print(f"LLM provider: Ollama (model: {settings.model_name})")
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
