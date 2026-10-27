import json
import sqlite3
from datetime import date

import anthropic

from . import tools

MODEL = "claude-haiku-5-5"
MAX_TOOL_ROUNDS = 5  # stop runaway loops: at most 5 rounds of tool calls per question

SYSTEM_PROMPT = """You answer questions about the user's own Spotify listening history using the provided tools.

- Today's date is {today}. Turn relative dates like "this summer" or "last month" into YYYY-MM-DD.
- The data covers {first_day} to {last_day}. If a question asks about time outside that range, say so.
- Plays under 30 seconds count as skips and are excluded from every number.
- If you're not sure of an artist's exact name, call search_artists first.
- Only state numbers that came from a tool result. If the tools can't answer a question (genres, moods, BPM, recommendations), say so plainly instead of guessing.
- Keep answers short and conversational."""

DATE_PROPS = {
    "start": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD. Omit for all time."},
    "end": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD. Omit for all time."},
}

TOOL_DEFINITIONS = [
    {
        "name": "top_artists",
        "description": "Top artists ranked by hours listened, with play counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                **DATE_PROPS,
                "limit": {"type": "integer", "description": "How many artists to return. Default 10."},
            },
        },
    },
    {
        "name": "top_tracks",
        "description": "Top tracks ranked by play count, optionally for one artist.",
        "input_schema": {
            "type": "object",
            "properties": {
                **DATE_PROPS,
                "limit": {"type": "integer", "description": "How many tracks to return. Default 10."},
                "artist": {"type": "string", "description": "Exact artist name (case-insensitive)."},
            },
        },
    },
    {
        "name": "listening_time",
        "description": "Total plays and hours, plus first and last play time. Filter by artist and/or track, or omit both for overall totals.",
        "input_schema": {
            "type": "object",
            "properties": {
                **DATE_PROPS,
                "artist": {"type": "string", "description": "Exact artist name (case-insensitive)."},
                "track": {"type": "string", "description": "Exact track name (case-insensitive)."},
            },
        },
    },
    {
        "name": "plays_over_time",
        "description": "Plays and hours grouped by month (YYYY-MM), weekday (0=Sunday) or hour of day (00-23, UTC). Use for trends and habits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "granularity": {"type": "string", "enum": ["month", "weekday", "hour"]},
                **DATE_PROPS,
                "artist": {"type": "string", "description": "Exact artist name (case-insensitive)."},
            },
            "required": ["granularity"],
        },
    },
    {
        "name": "search_artists",
        "description": "Find artist names containing a search string. Use to get the exact spelling before calling other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Part of an artist name, e.g. 'stroke'."},
            },
            "required": ["query"],
        },
    },
]

TOOL_FUNCTIONS = {
    "top_artists": tools.top_artists,
    "top_tracks": tools.top_tracks,
    "listening_time": tools.listening_time,
    "plays_over_time": tools.plays_over_time,
    "search_artists": tools.search_artists,
}


def _system_prompt():
    totals = tools.listening_time()
    return SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        first_day=totals["first_played"][:10],
        last_day=totals["last_played"][:10],
    )


def _run_tool(name, args):
    """Run one tool Claude asked for. Returns (result_text, is_error)."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Unknown tool: {name}", True
    try:
        return json.dumps(fn(**args)), False
    except (TypeError, ValueError, sqlite3.Error) as e:
        return f"Error: {e}", True


def answer(question):
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    system = _system_prompt()
    messages = [{"role": "user", "content": question}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system,
            tools=TOOL_DEFINITIONS,
            output_config={"effort": "low"},
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return text or "Sorry, I couldn't come up with an answer to that."

        # Keep Claude's whole turn (including its tool_use blocks) in the history.
        messages.append({"role": "assistant", "content": response.content})

        results = []
        for block in response.content:
            if block.type == "tool_use":
                content, is_error = _run_tool(block.name, block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })
        messages.append({"role": "user", "content": results})

    return "Sorry, that question took too many steps. Try asking it more simply."