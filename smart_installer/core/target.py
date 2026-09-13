"""Target client source-tree inspection.

The patcher operates on a copy of a client's source tree.  Target discovers
what the client is, which language it is written in, where the interesting
integration points live, and whether the patterns have already been applied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

# Directories never traversed when indexing the tree.
IGNORED = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea",
    ".vscode", ".vs", "target", "vendor",
}

# Well-known client markers: filename -> which client claims it.
CLIENT_MARKERS: dict[str, str] = {
    "opencode-schema.json": "opencode",
    "go.mod": "opencode-guess",  # resolved by further inspection
}

# Signature files/keywords that identify a client even without its markers.
CLIENT_SIGNATURES: list[tuple[str, list[str]]] = [
    ("opencode", ["internal/llm/agent/agent.go", "internal/llm/prompt/coder.go", "internal/llm/tools"]),
    ("hermes", ["hermes/"]),
    ("aider", ["aider/__init__.py", "aider/coders/"]),
    ("claude-code", ["claude-code"]),
]


def iter_project_files(root: Path) -> Iterator[Path]:
    """Yield every interesting file under root, skipping ignored dirs."""
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        name = child.name
        if child.is_dir():
            if name in IGNORED or name.startswith("."):
                continue
            yield from iter_project_files(child)
        elif child.is_file() and not name.endswith((".pyc", ".pyo")):
            yield child


def detect_language(files: list[Path], root: Path) -> list[str]:
    """Bump a language tally from the files present."""
    tally: dict[str, int] = {}
    for f in files:
        suffix = f.suffix.lower()
        name = f.name.lower()
        if suffix == ".go":
            tally["+go"] = tally.get("+go", 0) + 1
        elif suffix == ".py":
            tally["+python"] = tally.get("+python", 0) + 1
        elif suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
            tally["+typescript"] = tally.get("+typescript", 0) + 1
        elif suffix == ".rs":
            tally["+rust"] = tally.get("+rust", 0) + 1
        elif suffix in (".md", ".json", ".yaml", ".yml", ".toml") or name in (
            "go.mod", "pyproject.toml", "Cargo.toml", "package.json"):
            # These are metadata, not code — don't inflate the count.
            pass
        elif suffix:
            tally["+other"] = tally.get("+other", 0) + 1
    ranked = sorted(tally, key=lambda k: tally[k], reverse=True)
    return ["go" if k == "+go" else "python" if k == "+python" else
            "typescript" if k == "+typescript" else "rust" if k == "+rust" else "other"
            for k in ranked]


def resolve_opencode_variant(root: Path) -> str:
    """Go modules could be opencode or something else; check package paths."""
    for f in (root / "internal" / "llm" / "prompt" / "coder.go").parent.iterdir() if (root / "internal" / "llm" / "prompt").is_dir() else []:
        _ = f
    go_mod = root / "go.mod"
    if go_mod.is_file():
        mod = go_mod.read_text(encoding="utf-8", errors="replace")
        if "opencode" in mod.lower():
            return "opencode"
    return "go"


def detect_client(root: Path) -> str:
    """Identify the client from well-known files and structure."""
    marker_hits = [CLIENT_MARKERS[n] for n in CLIENT_MARKERS if (root / n).is_file()]
    for guess in marker_hits:
        if guess == "opencode-guess":
            return resolve_opencode_variant(root)
        return guess

    rel_paths = {str(p.relative_to(root)).replace("\\", "/") for p in iter_project_files(root)}
    for client, sigs in CLIENT_SIGNATURES:
        if any(any(s in rp for rp in rel_paths) for s in sigs[0:1] if True):
            # require at least 2 signatures for confidence
            hits = sum(1 for sig in sigs if any(sig in rp for rp in rel_paths))
            if hits >= 2:
                return client
    return "generic"


class Target:
    """A client source tree being inspected/patched."""

    def __init__(self, path: str | Path):
        self.root = Path(path).expanduser().resolve()
        if not self.root.is_dir():
            raise NotADirectoryError(f"not a directory: {self.root}")
        self.files: list[Path] = list(iter_project_files(self.root))
        self.relative = [f.relative_to(self.root) for f in self.files]
        self.rel_str = [str(r).replace("\\", "/") for r in self.relative]
        self.rel_set = set(self.rel_str)
        self.languages = detect_language(self.files, self.root)
        self.client = detect_client(self.root)

    # -- convenience ----------------------------------------------------
    def has(self, rel: str) -> bool:
        return rel.replace("\\", "/") in self.rel_set

    def find(self, key: str) -> list[str]:
        """Return relative paths containing `key` as a path segment."""
        return [r for r in self.rel_str if key in r]

    def read(self, rel: str) -> Optional[str]:
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, IOError):
            return None

    def grep(self, rel: str, pattern: str, count: int = 3) -> list[str]:
        """Return up to `count` lines of rel containing pattern (line-match)."""
        content = self.read(rel)
        if content is None:
            return []
        return [ln for ln in content.splitlines() if pattern in ln][:count]

    def source_files(self) -> list[str]:
        """Relative paths of code files (the only places patterns apply)."""
        code = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".rb", ".java", ".c", ".h", ".cpp", ".hpp"}
        return [r for r in self.rel_str if any(r.endswith(x) for x in code)]

    def search(self, needle: str, limit_per_file: int = 2, files: Optional[list[str]] = None) -> list["Finding"]:
        """Grep every source file for a literal needle.

        Returns Findings with file + line number.  Feeds all probes so the
        pattern library stays client-agnostic.
        """
        from ..patterns.base import Finding

        out: list[Finding] = []
        src = files if files is not None else self.source_files()
        for rel in src:
            content = self.read(rel)
            if not content:
                continue
            hits = 0
            for idx, line in enumerate(content.splitlines(), 1):
                if needle in line:
                    out.append(Finding(file=rel, line=idx, evidence=line.strip()[:160]))
                    hits += 1
                    if hits >= limit_per_file:
                        break
        return out

    def describe(self) -> str:
        langs = ", ".join(self.languages) if self.languages else "unknown"
        return f"client={self.client!r} languages=[{langs}] files={len(self.files)} root={self.root}"