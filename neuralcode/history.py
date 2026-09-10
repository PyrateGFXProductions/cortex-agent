"""Keeping the transcript small enough to send.

Three mechanisms, cheapest first. Only the first two live here; the expensive
one is compact.py.

1. cap    - a fresh tool result is trimmed and the full text parked in a temp
            file the agent can page through. Free: the decision is made once,
            when the result is created, so it never edits the prefix.
2. strip  - once a turn is over, its tool results shrink to a stub. The edit
            lands at the tail, right before the next user message, so the
            cached prefix in front of it survives.
3. drop   - a single request is still too big. Throw tool results away whole,
            oldest first, until it fits.

Everything here refuses to touch the locked prefix - the frozen
system + summary + head that compaction leaves behind. That block has to stay
byte-identical to stay cached.
"""

import json
import tempfile
from pathlib import Path

from . import config

CAP = 10_000  # chars of a fresh tool result the agent sees inline
STUB = 300  # chars kept once the turn that produced it is over

TRIMMED = "[output trimmed:"  # marker, so stripping twice is a no-op
SUMMARY = "<summary>"  # marks the handoff note compaction leaves behind
SPILLS = []  # temp files belonging to the current turn

# Cache for locked(): keyed on len(messages) so it auto-invalidates when the
# list grows (new message appended) or shrinks (/rewind, compaction).
_LOCKED_CACHE: dict[int, int] = {}


# ------------------------------------------------------------------- 1. cap


def spill(text):
    """Park the full output on disk for the rest of this turn."""
    handle = tempfile.NamedTemporaryFile(
        mode="w", prefix="neuralcode-", suffix=".txt", delete=False
    )
    handle.write(text)
    handle.close()
    SPILLS.append(Path(handle.name))
    return handle.name


def cap(text):
    """Trim a fresh tool result, leaving a pointer to the whole thing."""
    if len(text) <= CAP:
        return text

    try:
        path = spill(text)
    except OSError:
        # No temp file (read-only /tmp, no space). Still better to trim and
        # say so than to fail the tool call outright.
        return text[:CAP] + f"\n\n{TRIMMED} {len(text) - CAP} chars cut and the rest could not be saved.]"
    return (
        text[:CAP] + f"\n\n{TRIMMED} {len(text) - CAP} of {len(text)} chars cut. "
        f"The whole output is at {path} - page through it with "
        "head, tail, sed -n or grep. It is deleted when this turn ends.]"
    )


def sweep():
    """Delete this turn's temp files. Their paths die with the tool results."""
    for path in SPILLS:
        path.unlink(missing_ok=True)
    SPILLS.clear()


# Register sweep as an atexit handler so spill files are removed even when
# the session is killed mid-turn (ctrl-c, OOM, etc.). Calling it again at
# normal turn-end is harmless - unlink(missing_ok=True) is idempotent.
import atexit as _atexit
_atexit.register(sweep)


def locked(messages):
    """Length of the frozen prefix - everything up to and including the newest
    summary. Derived rather than remembered, so it stays correct across
    /compact, /rewind and switching sessions.

    Result is cached by list length. The summary marker never moves once
    compaction has run, and appending new messages only grows the list, so
    a cached value for length N is still valid for length N+k - unless a
    rewind or compaction shrinks the list, at which point the key misses and
    we re-scan. This keeps the common case (append-only) at O(1).
    """
    key = len(messages)
    if key in _LOCKED_CACHE:
        return _LOCKED_CACHE[key]
    result = 0
    for index in range(key - 1, -1, -1):
        if SUMMARY in (messages[index].get("content") or ""):
            result = index + 1
            break
    _LOCKED_CACHE[key] = result
    return result


# ----------------------------------------------------------------- 2. strip


def strip(messages):
    """Shrink every tool result that is no longer part of the live turn.

    Called once a turn has finished, so by now "everything unlocked" and
    "everything the model no longer needs in full" are the same set.
    """
    shrunk = 0
    for message in messages[locked(messages):]:
        content = message.get("content") or ""
        if message["role"] != "tool" or TRIMMED in content or len(content) <= STUB:
            continue

        message["content"] = (
            content[:STUB] + f"\n\n{TRIMMED} {len(content) - STUB} more chars. "
            "Run the command again if you need them.]"
        )
        shrunk += 1
    return shrunk


# ------------------------------------------------------------------ 3. drop


def estimate(messages):
    """Rough token count. Good enough to decide whether to panic."""
    return sum(len(json.dumps(m)) for m in messages) // 4


def fit(messages):
    """Last resort: discard whole tool results, oldest first, until it fits.

    Returns how many went. Normally zero - cap and strip do the real work.
    """
    budget = config.CONTEXT_WINDOW * config.COMPACT_AT
    dropped = 0
    for message in messages[locked(messages):]:
        if estimate(messages) <= budget:
            break
        if message["role"] == "tool" and TRIMMED not in (message.get("content") or ""):
            message["content"] = f"{TRIMMED} dropped to fit the context window.]"
            dropped += 1
    return dropped
