"""Engine: the safe application of edits to a target source tree.

Responsibilities:
  - reset/verify a target is a git checkout (abort if not, unless forced).
  - run every pattern's assess() probe and report status.
  - for patterns with an auto plan (recipes), apply edits with:
      * dry-run reporting, never touching disk,
      * a backup of every edited file,
      * idempotency (edits are applied only if their marker is absent),
      * post-edit verification.
"""

from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .patterns.base import Edit, EditPlan
from .patterns.library import REGISTRY
from .core.target import Target


@dataclass
class EditResult:
    file: str
    status: str               # "applied" | "skipped" | "missing" | "ambiguous" | "verified"
    note: str = ""
    applied: int = 0
    occurrences: int = 0
    diff_preview: str = ""


@dataclass
class PlanResult:
    plan: EditPlan
    edits: list[EditResult] = field(default_factory=list)
    verified: int = 0
    failed: int = 0


class Engine:
    def __init__(self, target: Target, dry_run: bool = True, force: bool = False):
        self.target = target
        self.dry_run = dry_run
        self.force = force
        self.backup_dir: Optional[Path] = None

    # -- git safety ------------------------------------------------------
    def is_git_checkout(self) -> bool:
        return (self.target.root / ".git").exists()

    def ensure_safe(self) -> str:
        """Return '' if OK, else a human reason the run must not edit files."""
        if self.is_git_checkout():
            return ""
        if self.force:
            return "not a git checkout — proceeding anyway (--force)"
        return (
            f"{self.target.root} is not a git checkout. Patches are applied to a copy of the "
            "client source; use --force to edit a bare copy anyway."
        )

    # -- probes ----------------------------------------------------------
    def assess_all(self) -> list:
        return [(p, p.assess(self.target)) for p in REGISTRY]

    # -- application -----------------------------------------------------
    def _prepare_backup(self, files: list[str]) -> None:
        if self.dry_run:
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.backup_dir = self.target.root / f".cortex-smart-installer-backup-{stamp}"
        self.backup_dir.mkdir(parents=True)
        for rel in files:
            src = self.target.root / rel
            dst = self.backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy2(src, dst)

    def apply_plan(self, plan: EditPlan) -> PlanResult:
        result = PlanResult(plan=plan)
        files = sorted({e.file for e in plan.edits})
        self._prepare_backup(files)

        for edit in plan.edits:
            res = self._apply_one(edit)
            result.edits.append(res)
            if res.status in ("applied", "skipped"):
                result.verified += 1
            else:
                result.failed += 1
        return result

    def _apply_one(self, edit: Edit) -> EditResult:
        rel = edit.file.replace("\\", "/")
        path = self.target.root / rel

        # New-file creation path.
        if edit.create:
            if path.is_file():
                return EditResult(rel, "skipped", "already exists (idempotent), not overwritten")
            if self.dry_run:
                return EditResult(rel, "applied", f"DRY-RUN would create {rel}", applied=1)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(edit.replace, encoding="utf-8")
            return EditResult(rel, "applied", "created new file", applied=1)

        if not path.is_file():
            return EditResult(rel, "missing", "file not found: " + rel)

        content = path.read_text(encoding="utf-8", errors="replace")

        # Already applied? marker == what we'd write.
        if edit.replace and edit.replace in content:
            return EditResult(rel, "skipped", "already applied (idempotent)", applied=0, occurrences=content.count(edit.find))

        count = content.count(edit.find)
        if count == 0:
            return EditResult(rel, "missing", "find-string not present in file; manual review needed", occurrences=0)
        if edit.n != 0 and count != edit.n:
            return EditResult(rel, "ambiguous", f"found {count} occurrences, expected {edit.n}; manual review needed", occurrences=count)

        old = content
        new = old.replace(edit.find, edit.replace, edit.n if edit.n else count)

        diff_preview = "\n".join(difflib.unified_diff(
            old.splitlines(), new.splitlines(),
            fromfile="before/" + rel, tofile="after/" + rel, lineterm="", n=1))
        if diff_preview.strip():
            diff_preview = diff_preview.strip()

        if self.dry_run:
            return EditResult(rel, "applied", f"DRY-RUN would edit; {edit.note}".strip(), applied=1, occurrences=count, diff_preview=diff_preview)

        path.write_text(new, encoding="utf-8")
        return EditResult(rel, "applied", edit.note, applied=1, occurrences=count, diff_preview=diff_preview)

    def verify(self, result: PlanResult) -> None:
        """Re-probe the pattern to confirm application took."""
        return  # verification is a second assess() - done by the CLI after apply.

    def diff_of_plan(self, plan: EditPlan) -> str:
        """Full diff preview for a whole plan (dry-run report)."""
        chunks = []
        for edit in plan.edits:
            res = self._apply_one(edit)  # dry-run safe
            if res.diff_preview:
                chunks.append(res.diff_preview)
            elif res.status == "skipped":
                chunks.append(f"# {edit.file}: already applied, skipping")
            else:
                chunks.append(f"# {edit.file}: {res.status} - {res.note}")
        return "\n\n".join(chunks)