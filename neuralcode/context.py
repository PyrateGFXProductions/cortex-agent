"""Late injection: a small block appended just before we send.

It goes at the END of the message list so the stable prefix in front of it
stays cached.
"""

import os
import subprocess
from datetime import datetime

from .todos import todos_prompt
from pathlib import Path

LABELS = {"M": "modified", "D": "deleted", "A": "added", "??": "new"}

# Cached once per process - the branch almost never changes mid-session.
_BRANCH: str | None = None


def git(command):
    result = subprocess.run(
        f"git {command}", shell=True, capture_output=True, text=True
    )
    return result.stdout


def git_branch() -> str:
    """Return the current branch, fetching once and caching for the session."""
    global _BRANCH
    if _BRANCH is None:
        _BRANCH = git("branch --show-current").strip() or "(detached)"
    return _BRANCH


def file_stat(path: str):
    """Return (mtime, size) for change detection - O(1) vs O(file_size) for MD5.

    Git itself uses this same optimisation: it only re-hashes a blob when the
    inode, mtime, or size has changed. We do the same here because we only
    need to know *that* something changed, not *what* the new hash is.
    """
    try:
        st = os.stat(path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def git_state():
    """path -> (git-status-code, (mtime, size)) for every file git sees as changed."""
    state = {}
    for line in git("status --porcelain").splitlines():
        path = line[3:]
        state[path] = (line[:2].strip(), file_stat(path))
    return state


LAST_STATE = git_state()


def file_changes():
    """Files whose status or stat moved since the previous turn."""
    global LAST_STATE
    now = git_state()
    changed = {p: v[0] for p, v in now.items() if LAST_STATE.get(p) != v}
    LAST_STATE = now
    return changed


def changes_note():
    changed = file_changes()
    if not changed:
        return ""
    lines = [f"{LABELS.get(code, code)}: {path}" for path, code in changed.items()]
    return (
        "\n<system-reminder>\n"
        "These files changed since your last turn. Read them again before "
        "editing:\n" + "\n".join(lines) + "\n</system-reminder>"
    )


def todos_note():
    plan = todos_prompt()
    return f"\n<todos>\n{plan}\n</todos>" if plan else ""


def reminder():
    """The block we append to the messages on every turn."""
    return {
        "role": "user",
        "content": (
            "<env>\n"
            f"time: {datetime.now():%Y-%m-%d %H:%M}\n"
            f"git branch: {git_branch()}\n"
            "</env>" + todos_note() + changes_note()
        ),
    }
