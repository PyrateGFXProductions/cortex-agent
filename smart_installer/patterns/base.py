"""Pattern definitions.

A Pattern knows how to (a) assess whether a client already has the
enhancement, (b) locate the integration points in a client-agnostic way, and
(c) either edit the source automatically or spell out precisely what to
change.  Patterns never mutate files themselves — they return an Assessment
and optionally an EditPlan; the engine applies it.

Tiers:
  auto    — safe to apply automatically once integration points are found.
  guided  — needs a human to decide how to wire into the client's loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    """One integration point found in the target tree."""

    file: str                 # relative path
    line: Optional[int] = None
    note: str = ""
    evidence: str = ""        # snippet of matched line, if any


@dataclass
class Assessment:
    """Result of probing a target for one pattern."""

    pattern: str
    status: str               # "applied" | "partial" | "absent" | "unknown"
    reason: str = ""
    findings: list[Finding] = field(default_factory=list)
    tier: str = "guided"


@dataclass
class Edit:
    """A single file mutation expressed as find/replace.

    If create=True the *replace* field is the full file content to write;
    the file is created only if it does not already exist (idempotent).
    """

    file: str
    find: str
    replace: str
    note: str = ""
    n: int = 1                # occurrences to replace (0 = all)
    create: bool = False      # write `replace` as a brand-new file if absent

    @property
    def applied_marker(self) -> str:
        return self.replace


@dataclass
class EditPlan:
    """Ordered edits produced by a pattern or recipe."""

    target: str               # client name the plan was built for
    pattern: str
    edits: list[Edit] = field(default_factory=list)
    note: str = ""


class Pattern:
    """Base class. Subclasses implement assess() and optionally plan()."""

    id: str = "override"
    name: str = "Override"
    tier: str = "guided"

    def assess(self, target) -> Assessment:  # noqa: D401
        raise NotImplementedError

    def plan(self, target) -> Optional[EditPlan]:
        """Return None if this pattern is guided rather than auto-appliable."""
        return None

    def guide(self, target) -> str:
        """Human instructions for applying this pattern to `target`."""
        return ""


# ---------------------------------------------------------------------------
# Summary helpers used by engine and CLI.

def summarize_plan(plan: EditPlan) -> list[str]:
    out = [f"[{plan.target}] {plan.pattern}: {len(plan.edits)} edit(s)"]
    for e in plan.edits:
        out.append(f"    {e.file}: {e.note or 'no note'}")
    return out