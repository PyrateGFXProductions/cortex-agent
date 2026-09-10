# cortex-agent

A minimal coding agent harness built to teach how coding agents work — context engineering, tool execution, sandboxing, compaction, and subagents, all in ~1,000 lines of plain Python.

Based on the [Neural Breakdown tutorial](https://youtu.be/Lu1UWqVTbQg) by AVB. Watch the full walkthrough, then read the code commit-by-commit to see how each piece was added.

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

Install the MCP adapter (no API key required — the MCP server only calls local tools):

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

Config file locations:

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

## Support

If you find this useful, consider supporting the original creator on Patreon:

[![Become a Patron](https://c5.patreon.com/external/logo/become_a_patron_button.png)](https://www.patreon.com/NeuralBreakdownwithAVB)
