# cortex-agent

A **reference implementation of context-window efficiency patterns** for AI coding agents.

Originally a minimal, self-contained coding agent harness (fork of [neuralcode](https://github.com/avbiswas/neural-code) by AVB). Now primarily serves as **documented, portable patterns** that can be applied to any client: opencode, hermes, claude-code, aider, etc.

The standalone agent (`uv run cortex-agent`) still works and demonstrates all patterns in action.

---

## Quick Start

### Standalone Agent (Python)

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

### Local LLM Inference Stack (Smart Installer)

Install an optimal local LLM stack (vLLM+LMCache, Ollama, or llama.cpp) automatically:

```bash
# Linux/macOS
./smart-install.sh

# Windows PowerShell
.\smart-install.ps1

# Preview what would be installed
python smart_installer/smart_install.py --dry-run --no-rich
```

This detects your hardware and installs the optimal stack with LMCache for KV cache offloading.

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

### Core Agent (cortex_agent/)
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

### Efficiency Patterns (Portable to Any Client)
See [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) for the five core patterns:
1. **Locked Prefix + Late Injection** — preserve prompt cache by never mutating cached messages
2. **Three-Tier Tool Output Degradation** — cap (10K) → strip (300 chars) → drop (emergency)
3. **Compaction with Prefix Rebuild** — summarize at 85% full, rebuild to 35%, new prefix cached
4. **Isolated Subagents** — fresh context window, read-only tools, 12-turn cap, only final answer returns
5. **File Staleness Detection** — `os.stat(mtime, size)` diff per turn, warn on stale reads

### Opencode Patch (Private)
The `../opencode-efficiency-patch/` applies all patterns to opencode:
- Hardware-aware automatic configuration (5 hardware profiles)
- Late injection, locked prefix, compaction trigger from config
- Bash 30K→10K, View 250KB→100KB/2000→500
- Task agent: 12-turn cap, no write tools, no subagents
- File staleness detection via `os.stat(mtime, size)`

### Smart Installer (New)
Cross-platform interactive installer for local LLM inference:
```bash
./smart-install.sh          # Linux/macOS
.\smart-install.ps1         # Windows
python smart_installer/smart_install.py --dry-run --no-rich  # Preview
```
- Detects hardware → recommends optimal stack (vLLM+LMCache, Ollama, llama.cpp)
- Interactive, user-controlled installation with confirmations
- Generates client configs for cortex-agent, opencode, Continue.dev
- Creates system services (systemd, launchd, Task Scheduler)

### WSL2 + vLLM + LMCache (Windows)
For vLLM + LMCache on Windows (requires Linux):
```powershell
.\setup-wsl2-lmcache.ps1          # First run: installs WSL2, prompts reboot
.\setup-wsl2-lmcache.ps1 -SkipWSLInstall  # After reboot: completes inside WSL
```
See [`WSL2-LMCACHE-SETUP.md`](WSL2-LMCACHE-SETUP.md) for details.

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

## Documentation

| File | Description |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Complete project documentation for AI harnesses |
| [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) | Five core patterns + hardware-aware config + smart installer |
| [`WSL2-LMCACHE-SETUP.md`](WSL2-LMCACHE-SETUP.md) | WSL2 + vLLM + LMCache setup for Windows |
| [`smart_installer/README.md`](smart_installer/README.md) | Smart installer documentation |

---

## Credits & Attribution

This project stands on the shoulders of giants. We gratefully acknowledge the following projects and authors:

### Core Inspiration & Base Code
- **[neuralcode / neural-code](https://github.com/avbiswas/neural-code)** by **AVB (Avik Biswas)** — The original minimal coding agent harness and [Neural Breakdown tutorial](https://youtu.be/Lu1UWqVTbQg) that started this fork. The tutorial's commit-by-commit walkthrough is an exceptional educational resource for understanding how coding agents work from first principles.

### AI Coding Agent Ecosystem
- **[opencode](https://github.com/opencode-ai/opencode)** (now [charmbracelet/crush](https://github.com/charmbracelet/crush)) — The Go-based AI coding agent whose architecture inspired the efficiency pattern port; a production-grade reference for agent loops, tool systems, and session management.
- **[MCP (Model Context Protocol)](https://modelcontextprotocol.io/)** by **Anthropic** — The open protocol enabling tool exposure to Claude Desktop, Cursor, Windsurf, and other clients.

### Local LLM Inference Stack
- **[vLLM](https://github.com/vllm-project/vllm)** by **vLLM Team** — High-throughput LLM serving engine with PagedAttention, continuous batching, and prefix caching. The foundation for GPU-accelerated local inference.
- **[LMCache](https://github.com/LMCache/LMCache)** by **LMCache Team (Yihua Cheng, Yuhan Liu, et al.)** — KV cache management layer enabling persistent, tiered cache offloading and reuse across requests/sessions. Critical for multi-turn agentic workloads.
- **[Ollama](https://github.com/ollama/ollama)** by **Ollama Team** — Native cross-platform LLM runner with excellent quantization support and simple UX. The go-to for Apple Silicon and Windows native inference.
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** by **Georgi Gerganov** — The foundational CPU/GPU inference engine via GGUF. Enables local LLMs on virtually any hardware.

### Python Ecosystem
- **[PyTorch](https://pytorch.org/)** by **PyTorch Team (Meta AI)** — The tensor computation backbone for vLLM, LMCache, and model loading.
- **[Rich](https://github.com/Textualize/rich)** by **Textualize (Will McGugan)** — Beautiful terminal formatting, tables, progress bars, and interactive UI for the smart installer.
- **[Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)** by **Jonathan Slenders** — Advanced interactive input with history, auto-completion, and key bindings for the agent REPL.
- **[OpenAI Python SDK](https://github.com/openai/openai-python)** by **OpenAI** — The standard client interface for OpenAI-compatible APIs (used by all local inference servers).
- **[uv](https://github.com/astral-sh/uv)** by **Astral (Charlie Marsh)** — Fast Python package installer and resolver; replaces pip/venv/pipx for modern Python workflows.

### Infrastructure & Protocols
- **[Hugging Face Hub](https://huggingface.co/)** — Model hosting, versioning, and distribution; the standard for open-weight model access.
- **[Git](https://git-scm.com/)** — Version control; used for repo detection, branch awareness, and session history.

### Educational Resources
- **[Neural Breakdown](https://www.youtube.com/@NeuralBreakdown)** by **AVB** — Deep-dive video series on building coding agents from scratch. Highly recommended for anyone wanting to understand the internals.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

If you find this useful, consider supporting the original creator on Patreon:

[![Become a Patron](https://c5.patreon.com/external/logo/become_a_patron_button.png)](https://www.patreon.com/NeuralBreakdownwithAVB)