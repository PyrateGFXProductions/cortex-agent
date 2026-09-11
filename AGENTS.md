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

---

## Enhanced: Hardware-Aware Configuration (opencode patch)

The private opencode patch at `../opencode-efficiency-patch/` adds **hardware-aware automatic configuration** that detects your GPU/CPU/RAM and sets optimal defaults:

| Hardware Profile | GPU VRAM | System RAM | Stack | Context | Quantization | CPU Offload |
|---|---|---|---|---|---|---|
| High-End | ≥24GB | ≥64GB | vLLM+LMCache | 128K+ | FP16 | 64GB |
| Mid-Range | 8-24GB | 32-64GB | vLLM+LMCache | 32-64K | FP16/8-bit | 32GB |
| Entry | 4-8GB | 16-32GB | vLLM+LMCache | 16-32K | 4-bit/8-bit | 16GB |
| Apple Silicon | Unified | ≥32GB | Ollama | 32K | Q4_K_M | 50% RAM |
| CPU Only | None | ≥16GB | llama.cpp | 8-16K | Q4_K_M | N/A |

### Opencode Patch Enhancements

The patch applies all 5 efficiency patterns to opencode (Go):

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

## Enhanced: Smart Installer (new)

`smart_installer/` — **Cross-platform interactive installer** that detects hardware and installs the optimal local LLM stack with LMCache.

### Features
- **Hardware detection** — GPU vendor/model/VRAM, CPU, RAM, OS
- **Interactive stack selection** — vLLM+LMCache (NVIDIA/AMD GPU), Ollama (Apple Silicon/Windows), llama.cpp (CPU-only)
- **User-controlled** — Every step asks for confirmation; nothing installs without explicit "yes"
- **Auto-configures** — Context window, GPU memory, CPU offload, quantization based on hardware
- **Generates client configs** — cortex-agent, opencode, Continue.dev, generic OpenAI-compatible
- **Creates services** — systemd (Linux/WSL2), launchd (macOS), Task Scheduler (Windows)

### Usage
```bash
# Linux/macOS
./smart-install.sh

# Windows PowerShell
.\smart-install.ps1

# Preview only
python smart_installer/smart_install.py --dry-run --no-rich
```

### Output
Installs to `~/.llm-stack/` with:
- Python venv + PyTorch + vLLM/Ollama/llama.cpp + LMCache
- Optimized configs (vLLM, LMCache, Ollama, llama.cpp)
- Launch scripts (`start.sh` / `start.ps1`)
- System service files (systemd / launchd)
- Client configs for cortex-agent, opencode, Continue.dev

---

## WSL2 + vLLM + LMCache Setup (Windows)

For Windows users wanting vLLM + LMCache (which requires Linux):

See [`WSL2-LMCACHE-SETUP.md`](WSL2-LMCACHE-SETUP.md) for a one-command PowerShell script that:
1. Installs WSL2 Ubuntu 24.04 with GPU passthrough
2. Configures 24GB RAM / 8GB swap via `.wslconfig`
3. Installs PyTorch CUDA 12.1, vLLM, LMCache in a venv
4. Creates systemd service for auto-start
5. Exposes API at `http://localhost:8000/v1`

Run:
```powershell
.\setup-wsl2-lmcache.ps1          # First run: installs WSL2, prompts reboot
.\setup-wsl2-lmcache.ps1 -SkipWSLInstall  # After reboot: completes inside WSL
```

---

## Credits & Attribution

This project builds on exceptional work from the open-source community. Full attribution in [README.md#credits--attribution](README.md#credits--attribution).

**Key dependencies:**
- **Base fork:** [avbiswas/neural-code](https://github.com/avbiswas/neural-code) by **AVB** — original agent harness + Neural Breakdown tutorial
- **opencode** — Go agent architecture reference for efficiency pattern port
- **vLLM** — PagedAttention inference engine
- **LMCache** — KV cache offloading layer
- **Ollama** — Native cross-platform LLM runner
- **llama.cpp** — CPU/GPU GGUF inference engine
- **PyTorch, Rich, Prompt Toolkit, uv** — Python ecosystem foundations
- **MCP (Anthropic)** — Model Context Protocol for tool exposure

---

## License

MIT License — see [LICENSE](LICENSE) for details.