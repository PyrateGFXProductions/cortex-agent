# cortex-agent

A minimal coding agent harness built to teach how coding agents work — context engineering, tool execution, sandboxing, compaction, and subagents, all in ~1,000 lines of plain Python.

Based on the [Neural Breakdown tutorial](https://youtu.be/Lu1UWqVTbQg) by AVB. Watch the full walkthrough, then read the code commit-by-commit to see how each piece was added.

Fork of [avbiswas/neural-code](https://github.com/avbiswas/neural-code) — see [Changes from upstream](#changes-from-upstream) for what this fork adds.

https://github.com/user-attachments/assets/e4aaa9e4-69ec-40e3-8f5a-e4ec8c5b7208

---

## Install

```bash
# requires uv — https://docs.astral.sh/uv/getting-started/installation/
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
uv sync
```

Create `~/.agents/env` with your API credentials:

```bash
BASE_URL=https://openrouter.ai/api/v1
API_KEY=sk-or-...
MODEL=deepseek/deepseek-chat-v3-0324   # optional, this is the default
```

Run:

```bash
uv run cortex-agent
# or, after uv tool install .:
cortex-agent
```

---

## Use with Claude Desktop, Cursor, Windsurf, VS Code

Install the MCP adapter — **no API key required**, the MCP server only calls local tools:

```bash
pip install -e ".[mcp]"
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "cortex-agent": {
      "command": "cortex-agent-mcp"
    }
  }
}
```

| Client | Config file |
|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_settings.json` |

The MCP server exposes: `bash`, `read_file`, `write_file`, `str_replace`, `read_skill`.

---

## Features

- Interactive terminal chat with syntax-highlighted output
- Tools: shell commands, file read/write, targeted edits, skill files, subagents
- Permissions layer: allow/ask/deny rules for bash commands
- Shell sandbox on macOS (seatbelt) and Linux (bubblewrap); graceful fallback on Windows
- Skills loaded from `~/.agents/skills/` and `.agents/skills/`
- Subagents: exploration in a separate context window — findings only come back
- Todo tracking for multi-step tasks, re-injected every turn
- Saved sessions with `/sessions`, `/rewind`, `/compact`
- Automatic context compaction (85% → 35%) preserving prefix cache
- Git branch and stale-file alerts injected before each LLM call
- MCP server for Claude Desktop, Cursor, Windsurf, and other clients

---

## Skills

Skills are markdown instruction files the agent loads on demand. Drop them in:

```
~/.agents/skills/<name>/SKILL.md
.agents/skills/<name>/SKILL.md   # project-local
```

The agent sees the name and description in its system prompt and calls `read_skill` when it needs the full instructions.

---

## Changes from upstream

This fork ([avbiswas/neural-code](https://github.com/avbiswas/neural-code)) adds the following on top of the original tutorial codebase:

### Package identity
- Renamed Python package from `neuralcode` to `cortex_agent`; CLI command from `neuralcode` to `cortex-agent`
- Version bumped to `0.2.0`

### MCP server (`cortex_agent/mcp_server.py`) — new file
- Exposes `bash`, `read_file`, `write_file`, `str_replace`, `read_skill` via the Model Context Protocol
- Works with Claude Desktop, Cursor, Windsurf, VS Code (Continue), and any other MCP-compatible client
- Zero API key required — the MCP server only runs local tools; the client's own LLM handles the AI side
- Installed as a separate entry point: `cortex-agent-mcp`

### Distribution files — new files
- `AGENTS.md` — read automatically by Claude Code, OpenCode, Aider, and other harnesses
- `install.sh` / `install.ps1` — one-command setup for Mac/Linux/Windows; creates `~/.agents/env`, prints MCP config snippet

### Performance fixes (`context.py`, `history.py`, `session.py`, `tools.py`)

| File | Issue | Fix |
|---|---|---|
| `context.py` | MD5 hash of every git-changed file on every turn | `os.stat()` `(mtime, size)` — same semantics, O(1) per file |
| `context.py` | `git branch` subprocess on every turn | Cached in `_BRANCH` after first call |
| `history.py` | `locked()` full reverse-scan on every `strip()`/`fit()` call | Dict cache keyed on `len(messages)`; O(1) for append-only sessions |
| `history.py` | Temp spill files left on disk if session is killed mid-turn | `atexit.register(sweep)` guarantees cleanup on any exit |
| `session.py` | `all_sessions()` fully replayed every JSONL file to get a title | `title_from_file()` stops at the first user message line |
| `tools.py` | `str_replace` double-scanned file with `count()` then `replace()` | `find()`-based single-pass validation; slice-concat write |

### Repository hygiene
- Removed dead code: `neuralcode/intelligence/` (pressure_response.py referenced a non-existent base class), `GLOBAL_DISTRIBUTION_GUIDE.md` (planning document committed by mistake)
- Added `.vs/` to `.gitignore`
- Regenerated `uv.lock` to eliminate duplicate package entry

---

## Support

If you find this useful, consider supporting the original creator on Patreon:

[![Become a Patron](https://c5.patreon.com/external/logo/become_a_patron_button.png)](https://www.patreon.com/NeuralBreakdownwithAVB)
