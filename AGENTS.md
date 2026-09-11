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

See [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) for the five core patterns:

1. **Locked Prefix + Late Injection** — preserve prompt cache by never mutating cached messages; inject env context ephemerally at send time
2. **Three-Tier Tool Output Degradation** — cap (10K) → strip (300 chars) → drop (emergency)
3. **Compaction with Prefix Rebuild** — summarize at 85% full, rebuild to 35%, new prefix cached
4. **Isolated Subagents** — fresh context window, read-only tools, 12-turn cap, only final answer returns
5. **File Staleness Detection** — `os.stat(mtime, size)` diff per turn, warn on stale reads

These patterns are language-agnostic. The reference implementation is in `cortex_agent/`; the opencode port is in `../opencode-efficiency-patch/` (private).

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
