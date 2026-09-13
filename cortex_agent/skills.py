from pathlib import Path

import yaml

SKILL_DIRS = [
    Path.cwd() / ".agents" / "skills",
    Path.home() / ".agents" / "skills",
]


def find_skills():
    """Map each skill name to its description and SKILL.md path."""
    skills = {}
    for directory in SKILL_DIRS:
        for path in sorted(directory.glob("*/SKILL.md")):
            parts = path.read_text(encoding="utf-8", errors="replace").split("---", 2)
            if len(parts) != 3:
                continue  # no frontmatter; not a valid skill
            meta = yaml.safe_load(parts[1])
            if not isinstance(meta, dict) or "name" not in meta or "description" not in meta:
                continue
            description = " ".join(meta["description"].split())
            skills[meta["name"]] = {"description": description, "path": path}
    return skills


_SKILLS_CACHE = None


def _get_skills():
    """Lazy-load skills to avoid import-time filesystem access."""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        _SKILLS_CACHE = find_skills()
    return _SKILLS_CACHE


def skills_prompt():
    return "\n".join(f"- {name}: {s['description']}" for name, s in _get_skills().items())


def read_skill(name: str) -> str:
    """Open a skill and return its full instructions."""
    skills = _get_skills()
    if name not in skills:
        return f"No skill named '{name}'."
    return skills[name]["path"].read_text(encoding="utf-8")
