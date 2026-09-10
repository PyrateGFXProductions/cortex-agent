# cortex-agent

A minimal, self-contained coding agent harness. Fork of [neuralcode](https://github.com/avbiswas/neural-code) by AVB, extended with performance fixes and MCP support.

## Working in this repo

- All agent logic lives in `cortex_agent/`
- Config: `~/.agents/env` — set `BASE_URL`, `API_KEY`, optionally `MODEL` and `CONTEXT_WINDOW`
- Skills: `~/.agents/skills/<name>/SKILL.md` or `.agents/skills/<name>/SKILL.md`
- Run: `cortex-agent` (after install) or `uv run cortex-agent`

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
