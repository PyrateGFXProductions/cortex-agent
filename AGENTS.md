# cortex-agent

A **reference implementation of context-window efficiency patterns** for AI coding agents.

Originally a minimal, self-contained coding agent harness (fork of [neuralcode](https://github.com/avbiswas/neural-code) by AVB). Now primarily serves as **documented, portable patterns** that can be applied to any client: opencode, hermes, claude-code, aider, etc.

The standalone agent (`uv run cortex-agent`) still works and demonstrates all patterns in action.

## Working in this repo

- All agent logic lives in `cortex_agent/`
- Config: `~/.agents/env` — set `BASE_URL`, `API_KEY`, optionally `MODEL` and `CONTEXT_WINDOW`
- Skills: `~/.agents/skills/<name>/SKILL.md` or `.agents/skills/<name>/SKILL.md`
- Run: `cortex-agent` (after install) or `uv run cortex-agent`

## Efficiency Patterns (Portable to Any Client)

See [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) for the six core patterns:

1. **Locked Prefix + Late Injection** — preserve prompt cache by never mutating cached messages; inject env context ephemerally at send time
2. **Three-Tier Tool Output Degradation** — cap (10K) → strip (300 chars) → drop (emergency)
3. **Compaction with Prefix Rebuild** — summarize at 85% full, rebuild to 35%, new prefix cached
4. **Isolated Subagents** — fresh context window, read-only tools, 12-turn cap, only final answer returns
5. **File Staleness Detection** — `os.stat(mtime, size)` diff per turn, warn on stale reads
6. **Hardware-Aware Automatic Configuration** — detect GPU/CPU/RAM at startup, set optimal context/limits by profile

These patterns are language-agnostic. The reference implementation is in `cortex_agent/`; `smart_installer/` probes a target client's source tree, prints porting guidance, and applies a verified recipe (opencode shipped) automatically.

## Architecture

```
cortex_agent/
  agent.py        # main loop: input → LLM → tools → repeat
  llm.py          # system prompt + call_llm()
  tools.py        # bash, read_file, write_file, str_replace, read_skill, task
  history.py      # cap / strip / drop — keeps context window from overflowing
  compact.py      # summarise-and-rewind when the window fills past 85%
  context.py      # late injection: time, git branch, todos, stale-file alerts
  permissions.py  # allow/deny/ask rules for bash commands
  sandbox.py      # kernel-enforced sandbox (macOS: seatbelt, Linux: bubblewrap)
  session.py      # append-only JSONL transcripts in ~/.agents/sessions/
  subagent.py     # task tool: fresh agent loop in its own context window
  skills.py       # discover and load SKILL.md files
  todos.py        # in-memory todo list, injected every turn
  commands.py     # /compact /rewind /sessions slash commands
  ui.py           # rich terminal output
  prompt.py       # prompt_toolkit input with history and word-jump keys
  mcp_server.py   # MCP adapter — exposes tools to Claude Desktop, Cursor, etc.
```

## Key design constraints

- **Never break the prefix cache.** The cached prefix is `system + summary + locked head`. Anything that mutates those messages mid-session costs the entire prompt re-compute. Late injection (`context.reminder()`) appends to the tail specifically to avoid this.
- **Relative imports only.** All intra-package imports use `from . import ...` so the package can be renamed without touching import paths.
- **No frameworks.** Plain `openai` SDK, `rich`, `prompt_toolkit`. Nothing else for the core loop.

## Install for development

```bash
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
uv sync
uv run cortex-agent
```

## Installation Methods

See [README.md#installation-methods](README.md#installation-methods):

| Method | Best For | Command |
|--------|----------|---------|
| **uv (dev)** | Local development, contributing | `uv sync && uv run cortex-agent` |
| **uv tool (standard)** | System-wide install | `uv tool install ".[mcp]"` |
| **One-command installer** | Guided setup + `~/.agents/env` | `./install.sh` or `.\install.ps1` |
| **pip** | Existing environment | `pip install .` (or `.[mcp]`) |
| **PyInstaller binary** | Standalone binary from source | `uv run pyinstaller cortex-agent.spec` |

**Quick decision:**
- Local dev → `uv sync`
- System-wide → `uv tool install`
- First-time setup → `./install.sh` / `.\install.ps1`
- Standalone binary → `pyinstaller cortex-agent.spec`

> Docker images, package-manager packages, and prebuilt release binaries are planned but not published yet.

## MCP (use with Claude Desktop, Cursor, Windsurf, etc.)

```bash
pip install "cortex-agent[mcp]"  # or: pip install -e ".[mcp]" from source
```

Add to your MCP client config (no API key needed):

```json
{
  "mcpServers": {
    "cortex-agent": {
      "command": "cortex-agent-mcp"
    }
  }
}
```

Config file locations:
- **Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Cursor** — `~/.cursor/mcp.json`
- **Windsurf** — `~/.codeium/windsurf/mcp_settings.json`

## What this fork adds over upstream

### New: MCP server
`mcp_server.py` exposes the agent's tools — `bash`, `read_file`, `write_file`, `str_replace`,
`read_skill` — via the Model Context Protocol. Any MCP-compatible client (Claude Desktop,
Cursor, Windsurf, VS Code via Continue) can call these tools directly with no API key.

### New: Distribution files
- `install.sh` / `install.ps1` — one-command setup; installs the package, creates `~/.agents/env`
- `AGENTS.md` (this file) — read automatically by Claude Code, OpenCode, Aider

### Performance fixes applied to upstream code

| File | What changed |
|---|---|
| `context.py` | Replaced per-turn MD5 file hashing with `os.stat()` `(mtime, size)`. Cached git branch for the process lifetime. |
| `history.py` | `locked()` result cached by message list length (O(1) for append-only sessions). `sweep()` registered via `atexit` so spill files clean up on crash. |
| `session.py` | `all_sessions()` no longer replays entire JSONL files for titles; stops at first user message. |
| `tools.py` | `str_replace` uses `find()`-based single-pass validation instead of `count()` + `replace()` double-scan. |

### Package renamed
`neuralcode` → `cortex_agent` (Python package) / `cortex-agent` (CLI command).
All imports are relative so renaming touched only `pyproject.toml` and two string literals.

### Repository hygiene
- Removed dead code: `intelligence/pressure_response.py` (referenced non-existent base class)
- Removed `GLOBAL_DISTRIBUTION_GUIDE.md` (planning document committed by mistake)
- Added `.vs/` to `.gitignore`
- Regenerated `uv.lock` to clear duplicate package entry

---

## Enhanced: Smart Installer (new)

`smart_installer/` — a **source-code patcher** that implements the six
efficiency patterns into any AI coding client. It patches client source
(Go, Python, TypeScript, Rust — wherever the agent loop lives), it does not
install LLM stacks.

### What it does

- **Probe** — `python -m smart_installer <client-tree>` assesses which
  patterns already exist (`applied / partial / absent`) with hook points.
- **Guide** — `--guide` prints per-pattern porting instructions tuned to the
  detected language.
- **Recipe apply** — `--apply` applies a verified idempotent edit-plan for a
  known client. opencode is the shipped reference recipe; new clients are one
  recipe function in `smart_installer/recipes/__init__.py`.
- **Safe by default** — dry-run previews diffs, git-checkout required (unless
  `--force`), timestamped backups, re-run is a no-op (idempotent).

### Usage

```bash
python -m smart_installer ../opencode                 # probe
python -m smart_installer ../opencode --guide         # porting instructions
python -m smart_installer ../opencode --apply --dry-run  # preview diffs
python -m smart_installer ../opencode --apply         # apply for real
```

See `smart_installer/README.md` for the plugin API and safety semantics.

### Opencode Patch (reference recipe)

The recipe in `smart_installer/recipes/` is encoded from a tested Go patch
that applies all six patterns to opencode:

| Component | Enhancement |
|---|---|
| `internal/message/message.go` | `StripToolResults()` — post-turn strip to 300-char stubs; `FindLockedPrefix()` — O(1) locked prefix detection |
| `internal/llm/agent/agent.go` | Late injection (`buildLateInjection()`), turn-loop compaction trigger, `maxTurns` for task agent |
| `internal/llm/prompt/coder.go` | Removed env info from system prompt (moved to late injection) |
| `internal/llm/prompt/task.go` | Rewritten for strict isolation (no write tools, no subagents, 12-turn cap) |
| `internal/llm/tools/bash.go` | `MaxOutputLength` 30K → 10K (cap phase) |
| `internal/llm/tools/view.go` | `MaxReadSize` 250KB → 100KB, `DefaultReadLimit` 2000 → 500 (cap phase) |
| `internal/llm/agent/agent-tool.go` | Task agent created with `maxTurns=12` |
| `internal/tui/tui.go` | Auto-compact uses `config.Get().CompactAt` (default 0.95) |
| `internal/hardware/detect.go` | **New** — cross-platform GPU/CPU/RAM detection, 5 hardware profiles |
| `internal/config/config.go` | **New** — hardware-aware defaults via `applyHardwareDefaults()` |
| `internal/filetrack/tracker.go` | **New** — file staleness detection via `os.stat(mtime, size)` |
| `internal/filetrack/global.go` | **New** — global tracker for file read recording |

---

## Credits & Attribution

This project builds on exceptional work from the open-source community. Full attribution in [README.md#credits--attribution](README.md#credits--attribution).

**Project dependencies:** `openai`, `prompt-toolkit`, `rich`, `pyyaml` (runtime); `mcp` (optional). No LLM inference stack is bundled or installed — the agent talks to any OpenAI-compatible endpoint (`BASE_URL`), including optionally self-hosted vLLM/Ollama/llama.cpp backends.

**Built on:**
- **Base fork:** [avbiswas/neural-code](https://github.com/avbiswas/neural-code) by **AVB** — original agent harness + Neural Breakdown tutorial
- **opencode** — Go agent architecture reference for efficiency pattern port
- **vLLM / LMCache / Ollama / llama.cpp** — optional self-hosted inference backends the agent can point at (referenced by the hardware-aware config pattern)
- **MCP (Anthropic)** — Model Context Protocol for tool exposure

---

## Support

If cortex-agent has been useful to your workflow, consider supporting continued development:

[![Support me on Ko-fi](https://img.shields.io/badge/Support%20me%20on-Ko--fi-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/pyrategfxproductions)

---

## License

MIT License — see [LICENSE](LICENSE) for details. This fork is derived from
[neural-code](https://github.com/avbiswas/neural-code) by AVB; the original
work remains copyright of its author, and this fork's enhancements (MCP
server, smart installer, efficiency-pattern fixes, distribution files) are
contributed under the same MIT terms.