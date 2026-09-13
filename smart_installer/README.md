# Smart Installer — Cortex-Agent Efficiency Patcher

Takes the context-window efficiency enhancements from cortex-agent and **implements
them into any AI coding client** (opencode, hermes, aider, claude-code, custom
clients). Point it at a client source tree; it probes what's already there, then
either applies a verified recipe or gives you the exact porting instructions.

This is **not** an installer for LLM inference stacks — and it never chooses or
installs a model. A client already has its endpoint and model; this project only
changes how the client handles information.

## Two options

| Option | Command | What it does |
|--------|---------|--------------|
| **demo**  | `python -m smart_installer demo` | Set up the standalone demo client (`cortex-agent`). Discovers models already on the machine (Ollama's `ollama list`) and suggests them — never hardcodes one. |
| **patch** | `python -m smart_installer patch <client-tree>` | Apply the six efficiency patterns to an existing client's source code. |

## Quick Start

```bash
# Interactive menu (picks option 1 or 2)
python -m smart_installer

# Option 1: set up the demo client (discovers local models)
python -m smart_installer demo

# Option 2: probe a client source tree (no changes)
python -m smart_installer patch ../opencode

# Porting guidance for every pattern, hand-tuned to the detected language
python -m smart_installer patch ../opencode --guide

# Apply a verified recipe (dry-run first — shows every diff, writes nothing)
python -m smart_installer patch ../opencode --apply --dry-run

# Apply for real (git-checkout safety + timestamped backup + idempotent)
python -m smart_installer patch ../opencode --apply
```

## The Six Patterns

| # | Pattern | What it does |
|---|---------|--------------|
| 1 | Locked prefix + late injection | Never mutates the cached message prefix; injects env context as an ephemeral tail at send time |
| 2 | Three-tier tool output degradation | Cap (10K) → strip (300-char stub) → drop (emergency) on tool output |
| 3 | Compaction with prefix rebuild | At ~85% full, summarize to a handoff note; rebuild to ~35%; new prefix cached |
| 4 | Isolated subagents | Fresh context window, read-only tools, 12-turn cap; only final answer returns |
| 5 | File staleness detection | `os.stat(mtime, size)` diff per turn; warns on stale reads |
| 6 | Hardware-aware config | Detects GPU/RAM/CPU at startup; applies optimal context/limits by profile |

## How It Works

```
smart_installer/
├── core/target.py      # client detection + source-tree index
├── detect/             # client / language detection
├── patterns/base.py    # Pattern API: assess() → plan() → guide()
├── patterns/library.py # the six probes (the plugin API)
├── recipes/            # per-client EditPlans; opencode is the shipped reference
├── engine.py           # dry-run, backup, idempotent apply, diff preview
└── __main__.py         # CLI
```

### Two modes

1. **`demo`** — configures the standalone demo client. Never hardcodes a model:
   it discovers models already on the machine (Ollama) and suggests them.

2. **`patch`** — against any client tree:
   - **Probe + guide** (default, always available): assesses each pattern against
     any client tree regardless of language, reports `applied / partial / absent`,
     and prints concrete porting instructions quoting the reference implementation.
   - **Recipe apply** (for known clients): a recipe is an order-independent set of
     find/replace edits plus new-file creation. Every edit is checked for its
     marker before applying (idempotent), every touched file is backed up to
     `.cortex-smart-installer-backup-<timestamp>/`, and a git-checkout check runs
     first. Dry-run shows unified diffs without touching disk.

## Adding a New Client Recipe

Recipes live in `smart_installer/recipes/__init__.py`. A recipe is one function:

```python
def hermes_recipe(target: Target) -> EditPlan:
    return EditPlan(
        target=target.client, pattern="all-six",
        edits=[
            Edit("hermes/agent.py",
                 find="MAX_OUTPUT = 30000",
                 replace="MAX_OUTPUT = 10000  # cortex-agent cap",
                 note="Pattern 2: cap tool output"),
            Edit("hermes/agent.py",
                 find="",
                 replace="# full new-file content",
                 note="Pattern 5: staleness tracker", create=True),
        ],
        note="hermes forward-port of the six efficiency patterns",
    )

RECIPES["hermes"] = hermes_recipe
```

Then `python -m smart_installer patch path/to/hermes --apply --dry-run` previews it.
Workflow: probe → guide → write edits into a recipe → dry-run → apply → verify
against a long session (`cache_read_tokens > 0`).

## Safety Properties

- **Preview before write** — `--apply --dry-run` shows the full diff; only a bare
  `--apply` writes to disk.
- **Git-checkout requirement** — refuses to edit a tree that isn't a git checkout
  unless `--force` is passed (e.g. a bare copy).
- **Timestamped backups** — every edited file is copied to a backup dir before
  modification.
- **Idempotent** — re-running skips edits whose markers are already present;
  verified above: `applied=0 already-present=10`.
- **Create-only new files** — new packages/files are never overwritten.

## Reference

Patterns documented in depth in `EFFICIENCY_PATTERNS.md`. The opencode recipe in
`recipes/` is encoded from a tested Go patch (filetrack/, hardware/, message.go,
agent.go, tool executors) and reproduces all six enhancements.