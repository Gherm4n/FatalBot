"""Ollama model setup and LangGraph streaming workflow."""

from __future__ import annotations

from typing import Any, AsyncIterator, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from .config import settings


class ChatState(TypedDict):
    history: list[BaseMessage]
    message: str
    instructions: str
    reply: str


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{instructions}"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{message}"),
    ]
)


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content) if content is not None else ""


def create_chat_model() -> BaseChatModel:
    return ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_base_url,
        reasoning=False,
        temperature=0.8,
        num_predict=350,
    )


chat_model = create_chat_model()


async def ask_model(state: ChatState) -> dict[str, str]:
    prompt = PROMPT.invoke(
        {
            "instructions": state["instructions"],
            "history": state["history"],
            "message": state["message"],
        }
    )
    response = await chat_model.ainvoke(prompt)
    return {"reply": content_text(response.content).strip()}


def create_chat_graph():
    builder = StateGraph(ChatState)
    builder.add_node("fatalbot", ask_model)
    builder.add_edge(START, "fatalbot")
    builder.add_edge("fatalbot", END)
    return builder.compile()


chat_graph = create_chat_graph()


async def stream_reply(
    history: list[BaseMessage], message: str, instructions: str
) -> AsyncIterator[str]:
    state: ChatState = {
        "history": history,
        "message": message,
        "instructions": instructions,
        "reply": "",
    }
    async for chunk, metadata in chat_graph.astream(state, stream_mode="messages"):
        if metadata.get("langgraph_node") != "fatalbot":
            continue
        token = content_text(chunk.content)
        if token:
            yield token

