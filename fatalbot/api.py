"""FastAPI routes and the NDJSON streaming protocol."""

from __future__ import annotations

import json
import random
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR, club_info, settings
from .llm import stream_reply
from .prompts import build_system_prompt
from .schemas import ChatRequest
from .sessions import RoundFinished, SessionBusy, session_store


app = FastAPI(title="FatalBot", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def ndjson(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "provider": "ollama", "model": settings.model_name}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {
        "clubName": club_info.name,
        "welcome": club_info.welcome,
        "maxAttempts": settings.max_attempts,
    }


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    session_id, _ = session_store.create()
    return {"sessionId": session_id, "attempts": 0, "won": False}


@app.post("/api/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(message) > settings.max_message_length:
        raise HTTPException(
            status_code=400,
            detail=f"Message is limited to {settings.max_message_length} characters",
        )

    try:
        attempt = session_store.start_attempt(body.sessionId)
    except (RoundFinished, SessionBusy) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    club_fact = random.choice(club_info.facts)

    async def generate() -> AsyncIterator[str]:
        reply_parts: list[str] = []
        completed = False
        try:
            yield ndjson(
                {
                    "type": "start",
                    "sessionId": attempt.session_id,
                    "attempts": attempt.number,
                }
            )
            instructions = build_system_prompt(club_fact)
            async for token in stream_reply(attempt.history, message, instructions):
                reply_parts.append(token)
                yield ndjson({"type": "token", "content": token})

            reply = "".join(reply_parts).strip()
            if not reply:
                raise RuntimeError("Ollama returned an empty response")

            # Game code, never the model, decides if the exact flag leaked.
            won = session_store.complete_attempt(attempt, message, reply)
            completed = True
            round_over = attempt.session.finished
            yield ndjson(
                {
                    "type": "done",
                    "attempts": attempt.number,
                    "attemptsRemaining": settings.max_attempts - attempt.number,
                    "won": won,
                    "roundOver": round_over,
                    "flag": settings.flag if won else None,
                }
            )
        except Exception as exc:
            yield ndjson(
                {"type": "error", "message": f"Could not get an Ollama reply: {exc}"}
            )
        finally:
            # Also runs when the browser disconnects and cancels the generator.
            if not completed:
                session_store.fail_attempt(attempt)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Content-Type": "application/x-ndjson; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )
