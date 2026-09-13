import json
import os

from openai import OpenAI

from . import config
from .skills import skills_prompt
from .tools import TOOLS, TOOL_SCHEMAS

_client = None


def _get_client():
    """Lazy-initialise the OpenAI client.

    Deferred until first call so the setup wizard can write ~/.agents/env
    and reload config before the client is created with the real credentials.
    """
    global _client
    if _client is None:
        # Re-read config in case the wizard set os.environ after import time.
        from . import config as _cfg
        import importlib
        importlib.reload(_cfg)
        _client = OpenAI(base_url=_cfg.BASE_URL, api_key=_cfg.API_KEY)
    return _client


def get_client():
    """Get the OpenAI client (lazy initialization)."""
    return _get_client()

def _build_system_prompt() -> str:
    """Build system prompt lazily to avoid import-time filesystem access."""
    return f"""
You are a coding agent. Your job is to code. Always code.
Use the bash tool to inspect files.
Use write_file to create files and str_replace to edit them.
Answer back to the user once exploration is done.

For any task that takes more than one step, call write_todos first and plan it
out. Send the whole list every time you call it - it replaces the old one.
Keep exactly one task in_progress, mark it done the moment it is finished, and
move the next one to in_progress in the same call. Do not batch up completions
at the end. Skip the tool entirely for single-step tasks; it is noise there.

The current list is injected back to you every turn inside <todos> tags, so
that block - not the transcript - is the truth about where you are.

When you need to understand how something works - where a feature lives, how
data flows, what calls what - send a task subagent instead of grepping your
way there yourself. It explores in its own context window and hands you back
just the findings, so the search does not fill yours. It cannot see this
conversation, so write the question so it stands alone. Do all editing
yourself; the subagent only reads.

Long tool output is cut short, and the whole thing is written to a temp file
whose path is given at the cut. Page through it with head, tail, sed -n or
grep rather than asking for it again. That file only exists for the current
turn, so read it now or re-run the command later.

Your current working directory is: {os.getcwd()}

You have skills available. Each one is a set of instructions for a task.
If a skill matches what the user wants, call read_skill first and follow it.

{skills_prompt()}
"""


_SYSTEM_PROMPT_CACHE = None


def get_system_prompt() -> str:
    """Get system prompt, building it lazily on first access."""
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is None:
        _SYSTEM_PROMPT_CACHE = _build_system_prompt()
    return _SYSTEM_PROMPT_CACHE


def call_llm(messages, tools=None):
    if not config.MODEL:
        raise RuntimeError(
            "No model configured. Set MODEL in ~/.agents/env, or run the "
            "setup wizard (`cortex-agent` / `python -m smart_installer demo`) "
            "to pick one — the installer discovers models already on the machine."
        )
    response = _get_client().chat.completions.create(
        model=config.MODEL,
        messages=messages,
        tools=tools or TOOL_SCHEMAS,
    )

    message = response.choices[0].message

    completion_details = response.usage.completion_tokens_details
    prompt_details = response.usage.prompt_tokens_details

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
        "cached_tokens": getattr(prompt_details, "cached_tokens", None),
    }

    return message, usage


if __name__ == "__main__":
    user_input = input("Enter your prompt> ")

    message, usage = call_llm([
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_input},
    ])

    print("\nAgent: ", message.content, "\n")

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        result = TOOLS[tool_call.function.name](**args)
        print("Tool: ", tool_call.function.name, args)
        print(result, "\n")

    print(usage)
