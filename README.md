# cortex-agent

[![cortex-agent](PGFX_Cortex_Agent_logo.jpg)](PGFX_Cortex_Agent_logo.jpg)

> **Reference implementation of context-window efficiency patterns for AI coding agents** — locked prefix + late injection, three-tier tool output degradation, compaction with prefix rebuild, isolated subagents, file staleness detection, hardware-aware automatic configuration — plus a smart installer that patches any client's source to adopt them.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-DE5FE9.svg)](https://docs.astral.sh/uv/)

---

## What is this?

**cortex-agent** began as a minimal, self-contained coding agent harness (fork of [neuralcode](https://github.com/avbiswas/neural-code) by AVB). It has evolved into a **reference implementation of context-window efficiency patterns** — documented, portable techniques that can be applied to any AI coding client (opencode, hermes, claude-code, aider, etc.).

The standalone agent (`uv run cortex-agent`) still works and demonstrates all patterns in action. But the primary value is the **architecture** — six core efficiency patterns plus a source-code patcher — that other clients can adopt.

---

## Efficiency Patterns (Portable to Any Client)

See [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) for complete documentation.

| Pattern | What It Solves | Key Insight |
|---------|----------------|-------------|
| **1. Locked Prefix + Late Injection** | Prompt cache invalidation | Never mutate cached messages; inject env context (time, git, todos) as ephemeral tail message at send time |
| **2. Three-Tier Tool Output Degradation** | Context window overflow | Cap (10K) → Strip (300 chars) → Drop (emergency) — progressive, idempotent, cache-safe |
| **3. Compaction with Prefix Rebuild** | Long sessions | Summarize at 85% full, rebuild to 35%, new `system + summary` becomes locked prefix |
| **4. Isolated Subagents** | Exploration token burn | Fresh context window, read-only tools, 12-turn cap, only final answer returns |
| **5. File Staleness Detection** | Stale reads | `os.stat(mtime, size)` diff per turn, warns agent before editing changed files |
| **6. Hardware-Aware Configuration** | Per-machine ergonomics | Detects GPU/CPU/RAM at startup, applies optimal context/turn limits by profile |

**Also included:** the **Smart Installer** (`smart_installer/`) — a source-code patcher that probes a client's tree, prints porting guidance per pattern, and applies a verified idempotent recipe (opencode shipped) with dry-run, backups, and git-checkout safety.

---

## Quick Start

### Standalone Agent (Python)

```bash
# requires uv — https://docs.astral.sh/uv/getting-started/installation/
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
uv sync

# Create ~/.agents/env with your API credentials
cat > ~/.agents/env << 'EOF'
BASE_URL=https://openrouter.ai/api/v1
API_KEY=sk-or-...
MODEL=deepseek/deepseek-v4-flash   # optional, this is the default
EOF

uv run cortex-agent
```

### Apply Patterns to Another Client (Smart Installer)

Cortex-agent is a reference implementation; adopt its patterns in opencode, hermes, aider, or your own client:

```bash
python -m smart_installer path/to/opencode              # probe: what's applied / partial / absent
python -m smart_installer path/to/opencode --guide      # per-pattern porting instructions
python -m smart_installer path/to/opencode --apply --dry-run  # preview exact diffs
python -m smart_installer path/to/opencode --apply      # apply for real (idempotent)
```

This probes the client source tree, reports which of the six patterns already
exist, and can apply a verified recipe (opencode ships as the reference; new
clients are one function in `smart_installer/recipes/`). Preview with
`--apply --dry-run` (writes nothing); a real `--apply` is guarded by a
git-checkout requirement, writes timestamped backups, and re-runs are no-ops.

---

## Installation Methods

| Method | Best For | Command |
|--------|----------|---------|
| **uv (dev)** | Local development, contributing | `uv sync && uv run cortex-agent` |
| **uv tool (standard)** | System-wide install | `uv tool install ".[mcp]"` |
| **One-command installer** | Guided setup + `~/.agents/env` | `./install.sh` (macOS/Linux) or `.\install.ps1` (Windows) |
| **pip** | Existing environment | `pip install .` or `pip install -e ".[mcp]"` |
| **PyInstaller binary** | Build a standalone binary from source | `uv run pyinstaller cortex-agent.spec` |

### uv (development)

```bash
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
uv sync
uv run cortex-agent
```

### One-command installer

`install.sh` / `install.ps1` install the package (with the MCP adapter) as a `uv` tool and create `~/.agents/env`. On first run, `cortex-agent` launches an interactive setup wizard that walks you through picking a provider and entering your API key — no manual file editing required:

```bash
# macOS / Linux
./install.sh

# Windows PowerShell (from the repo root)
.\install.ps1
```

### PyInstaller binary

`cortex-agent.spec` builds a standalone binary (no Python needed on the target):

```bash
uv run pyinstaller cortex-agent.spec
# dist/cortex-agent        (macOS / Linux)
# dist/cortex-agent.exe    (Windows)
```

> Docker images, `apt`/`brew`/`scoop` packages, and prebuilt release binaries are **planned but not published yet**.

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

| Client | Config File |
|--------|-------------|
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Cursor** | `~/.cursor/mcp.json` |
| **Windsurf** | `~/.codeium/windsurf/mcp_settings.json` |

The MCP server exposes: `bash`, `read_file`, `write_file`, `str_replace`, `read_skill`.

The MCP server is **fail-closed**: there is no interactive approval, so any command that
would prompt in the CLI is refused instead, and `write_file`/`str_replace` are confined to
the directory the server was launched from. Use the interactive CLI for full control.

---

## Smart Installer (Source-Code Patcher)

`smart_installer/` implements the six efficiency patterns into any AI coding
client by patching its **source code** (Go, Python, TypeScript, Rust — wherever
the agent loop lives). It is not an LLM-stack installer.

```bash
# Linux/macOS / Windows PowerShell — from the repo root:
python -m smart_installer path/to/opencode                # probe
python -m smart_installer path/to/opencode --guide        # porting instructions
python -m smart_installer path/to/opencode --apply --dry-run  # preview diffs
python -m smart_installer path/to/opencode --apply        # apply for real
```

**What it does:**
1. **Probes** the target tree — reports each pattern as `applied / partial / absent` with hook points
2. **Guides** — per-pattern porting instructions tuned to the detected language
3. **Applies** — a verified, idempotent edit-plan for a known client (opencode ships as the reference recipe)
4. **Safeguards** — dry-run preview, git-checkout requirement (unless `--force`), timestamped backups, re-runs are no-ops

Adding a new client is one recipe function in `smart_installer/recipes/__init__.py`. See [`smart_installer/README.md`](smart_installer/README.md).

---

## Documentation

| File | Description |
|------|-------------|
| [`AGENTS.md`](AGENTS.md) | Complete project documentation for AI harnesses |
| [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) | The six patterns + patcher + opencode reference |
| [`smart_installer/README.md`](smart_installer/README.md) | Smart installer usage & plugin API |

---

## Credits & Attribution

This project builds on exceptional work from the open-source community:

### Core Inspiration & Base Code
- **[neuralcode / neural-code](https://github.com/avbiswas/neural-code)** by **AVB (Avik Biswas)** — The original minimal coding agent harness and [Neural Breakdown tutorial](https://youtu.be/Lu1UWqVTbQg). The tutorial's commit-by-commit walkthrough is an exceptional educational resource.

### AI Coding Agent Ecosystem
- **[opencode](https://github.com/opencode-ai/opencode)** (now [charmbracelet/crush](https://github.com/charmbracelet/crush)) — Go-based AI coding agent; architecture reference for efficiency pattern port.
- **[MCP (Model Context Protocol)](https://modelcontextprotocol.io/)** by **Anthropic** — Open protocol for tool exposure to Claude Desktop, Cursor, Windsurf.

### Optional Inference Backends (self-hosted, config only)
The agent is client-agnostic; it talks to any OpenAI-compatible endpoint. If you self-host a backend, these are common choices:
- **[vLLM](https://github.com/vllm-project/vllm)** by **vLLM Team** — High-throughput LLM serving with PagedAttention, continuous batching, prefix caching.
- **[LMCache](https://github.com/LMCache/LMCache)** by **LMCache Team (Yihua Cheng, Yuhan Liu, et al.)** — KV cache management layer for persistent, tiered cache offloading.
- **[Ollama](https://github.com/ollama/ollama)** by **Ollama Team** — Native cross-platform LLM runner with excellent quantization support.
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** by **Georgi Gerganov** — Foundational CPU/GPU inference engine via GGUF.

### Python Ecosystem
- **[Rich](https://github.com/Textualize/rich)** by **Textualize (Will McGugan)** — Beautiful terminal formatting, tables, progress bars.
- **[Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)** by **Jonathan Slenders** — Advanced interactive input for the agent REPL.
- **[OpenAI Python SDK](https://github.com/openai/openai-python)** by **OpenAI** — Standard client for OpenAI-compatible APIs.
- **[uv](https://github.com/astral-sh/uv)** by **Astral (Charlie Marsh)** — Fast Python package installer and resolver.

### Reference & Protocols
- **[Git](https://git-scm.com/)** — Version control; repo detection, branch awareness.

---

## Support This Project

If cortex-agent has been useful to your workflow, consider supporting continued development:

[![Support me on Ko-fi](https://img.shields.io/badge/Support%20me%20on-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/pyrategfxproductions)

[![YouTube](https://img.shields.io/badge/YouTube-PyrateGFXProductions-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@PyrateGFXProductions)
[![YouTube](https://img.shields.io/badge/YouTube-TwigandBerries-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@TwigandBerries)
[![Civitai](https://img.shields.io/badge/Civitai-PyrateGFXProductions-6D28D9?style=for-the-badge&logo=civitai&logoColor=white)](https://civitai.com/user/PyrateGFXProductions)

Your support helps fund new features, pattern research, and keeping the project maintained and free for everyone.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

This project is a fork of [neural-code](https://github.com/avbiswas/neural-code) by AVB, with enhancements (MCP server, smart installer, efficiency-pattern performance fixes, distribution files). The original work remains copyright of its author; the fork's enhancements are contributed under the same MIT terms.

---

## Disclaimer

This software is provided "as is," without warranty of any kind, express or implied. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability.

- **AI-generated content:** Output from integrated LLMs is generated by AI models. You are solely responsible for how you use, publish, or distribute AI-generated output.
- **Not affiliated:** This project is independent. Not affiliated with, endorsed by, or connected to any model vendor unless explicitly stated.
- **Model licensing:** If you run a local inference backend, review each model's license before commercial use.

---

*Built with obsessive attention to detail by PyrateGFX Productions.*