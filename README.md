# cortex-agent

[![cortex-agent](PGFX_Cortex_Agent_logo.jpg)](PGFX_Cortex_Agent_logo.jpg)

> **Reference implementation of context-window efficiency patterns for AI coding agents** — locked prefix + late injection, three-tier tool output degradation, compaction with prefix rebuild, isolated subagents, file staleness detection — plus a hardware-aware smart installer for local LLM inference stacks (vLLM+LMCache, Ollama, llama.cpp).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-DE5FE9.svg)](https://docs.astral.sh/uv/)

---

## What is this?

**cortex-agent** began as a minimal, self-contained coding agent harness (fork of [neuralcode](https://github.com/avbiswas/neural-code) by AVB). It has evolved into a **reference implementation of context-window efficiency patterns** — documented, portable techniques that can be applied to any AI coding client (opencode, hermes, claude-code, aider, etc.).

The standalone agent (`uv run cortex-agent`) still works and demonstrates all patterns in action. But the primary value is the **architecture** — five core efficiency patterns plus a hardware-aware installer — that other clients can adopt.

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

**Additional patterns implemented:**
- **Pattern 6: Hardware-Aware Automatic Configuration** — Detects GPU/CPU/RAM, maps to 5 profiles, auto-configures context window, quantization, GPU memory, CPU offload
- **Pattern 7: Interactive Smart Installer** — Cross-platform installer that detects hardware, presents options interactively, installs optimal local LLM stack

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
MODEL=deepseek/deepseek-chat-v3-0324   # optional, this is the default
EOF

uv run cortex-agent
```

### Local LLM Inference Stack (Smart Installer)

Install an optimal local LLM stack (vLLM+LMCache, Ollama, or llama.cpp) with LMCache KV cache offloading:

```bash
# Linux/macOS
./smart-install.sh

# Windows PowerShell
.\smart-install.ps1

# Preview what would be installed (no changes)
python smart_installer/smart_install.py --dry-run --no-rich
```

This detects your hardware and installs the optimal stack with LMCache for KV cache offloading.

---

## Installation Methods

Choose the method that fits your environment:

| Method | Best For | Command |
|--------|----------|---------|
| **Standard (uv)** | Local development, contributing | `uv sync` |
| **Docker** | CI/CD, reproducible envs, isolation | `docker run ...` |
| **Package Managers** | Quick system-wide install | `brew install ...` / `scoop install ...` |
| **Binary Releases** | Air-gapped, no toolchain, CI runners | `curl ... / cortex-agent` |
| **Kubernetes/Helm** | Production, team clusters, GitOps | `helm install ...` |
| **Devcontainers** | VS Code Remote, Codespaces, team consistency | "Reopen in Container" |
| **Cloud GPU** (RunPod, Lambda, Modal) | No local GPU, burst workloads | SSH + smart installer |
| **Air-gapped/Offline** | Secure/classified environments | `pip download --offline` |
| **Multi-user/Shared** | Team servers, shared GPU nodes | System-wide install |

### Docker

**CPU-only (works everywhere):**
```bash
docker run -it --rm \
  -v ~/.agents:/home/agent/.agents \
  -v $(pwd):/workspace \
  ghcr.io/pyrategfxproductions/cortex-agent:latest
```

**GPU (NVIDIA, requires nvidia-container-toolkit):**
```bash
docker run -it --rm --gpus all \
  -v ~/.agents:/home/agent/.agents \
  -v $(pwd):/workspace \
  ghcr.io/pyrategfxproductions/cortex-agent:cuda-latest
```

**With local LLM stack (vLLM + LMCache) via compose:**
```yaml
# docker-compose.yml
services:
  cortex-agent:
    image: ghcr.io/pyrategfxproductions/cortex-agent:cuda-latest
    runtime: nvidia
    environment:
      - BASE_URL=http://vllm:8000/v1
      - API_KEY=dummy
      - MODEL=local-model
    volumes:
      - ~/.agents:/home/agent/.agents
      - ./workspace:/workspace
    depends_on:
      - vllm

  vllm:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    command: >
      --model meta-llama/Llama-3.1-8B-Instruct
      --gpu-memory-utilization 0.85
      --max-model-len 32768
      --enable-prefix-caching
    ports:
      - "8000:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Package Managers

| Platform | Command |
|----------|---------|
| **macOS (Homebrew)** | `brew install pyrategfxproductions/tap/cortex-agent` |
| **Windows (Scoop)** | `scoop bucket add pyrategfx https://github.com/PyrateGFXProductions/scoop-bucket && scoop install cortex-agent` |
| **Windows (Chocolatey)** | `choco install cortex-agent` |
| **Arch Linux (AUR)** | `yay -S cortex-agent-git` |
| **Nix** | `nix run github:PyrateGFXProductions/cortex-agent` |

### Binary Releases

```bash
# Linux x86_64
curl -L -o cortex-agent https://github.com/PyrateGFXProductions/cortex-agent/releases/latest/download/cortex-agent-linux-x86_64
chmod +x cortex-agent && ./cortex-agent

# macOS (Apple Silicon)
curl -L -o cortex-agent https://github.com/PyrateGFXProductions/cortex-agent/releases/latest/download/cortex-agent-macos-arm64
chmod +x cortex-agent && ./cortex-agent

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/PyrateGFXProductions/cortex-agent/releases/latest/download/cortex-agent-windows-x86_64.exe" -OutFile "cortex-agent.exe"
.\cortex-agent.exe
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

| Client | Config File |
|--------|-------------|
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Cursor** | `~/.cursor/mcp.json` |
| **Windsurf** | `~/.codeium/windsurf/mcp_settings.json` |

The MCP server exposes: `bash`, `read_file`, `write_file`, `str_replace`, `read_skill`.

---

## Smart Installer (Local LLM Stack)

Cross-platform interactive installer that detects your hardware and installs the optimal local LLM inference stack with LMCache:

```bash
# Linux/macOS
./smart-install.sh

# Windows PowerShell
.\smart-install.ps1

# Preview only
python smart_installer/smart_install.py --dry-run --no-rich
```

**What it does:**
1. **Detects hardware** — GPU vendor/model/VRAM, CPU, RAM, OS
2. **Shows hardware summary** — asks for confirmation
3. **Interactive stack selection** — vLLM+LMCache (NVIDIA/AMD GPU), Ollama (Apple Silicon/Windows), llama.cpp (CPU-only)
4. **Interactive additional components** — CUDA/ROCm, Python venv, model pre-download, auto-start service
5. **Shows complete plan** — final confirmation before any installation
6. **Installs with progress** — generates all configs, services, client configs

**Hardware profiles & recommendations:**

| Your Hardware | Recommended Stack | Quantization | Context |
|---------------|-------------------|--------------|---------|
| RTX 4090 (24GB) | vLLM + LMCache | FP16 | 128K+ |
| RTX 3080/4080 (10-16GB) | vLLM + LMCache | FP16/8bit | 32-64K |
| RTX 3060/4060 (8-12GB) | vLLM + LMCache | 8bit/4bit | 16-32K |
| MacBook Pro M3 Max (96GB) | Ollama | Q4_K_M | 64K |
| MacBook Air M2 (16GB) | Ollama | Q4_K_M | 16K |
| No GPU (32GB RAM) | llama.cpp | Q4_K_M | 8-16K |

---

## WSL2 + vLLM + LMCache (Windows)

For Windows users wanting vLLM + LMCache (requires Linux):

```powershell
.\setup-wsl2-lmcache.ps1          # First run: installs WSL2, prompts reboot
.\setup-wsl2-lmcache.ps1 -SkipWSLInstall  # After reboot: completes inside WSL
```

See [`WSL2-LMCACHE-SETUP.md`](WSL2-LMCACHE-SETUP.md) for details.

---

## Documentation

| File | Description |
|------|-------------|
| [`AGENTS.md`](AGENTS.md) | Complete project documentation for AI harnesses |
| [`EFFICIENCY_PATTERNS.md`](EFFICIENCY_PATTERNS.md) | Five core patterns + hardware-aware config + smart installer |
| [`WSL2-LMCACHE-SETUP.md`](WSL2-LMCACHE-SETUP.md) | WSL2 + vLLM + LMCache setup for Windows |
| [`smart_installer/README.md`](smart_installer/README.md) | Smart installer documentation |

---

## Credits & Attribution

This project builds on exceptional work from the open-source community:

### Core Inspiration & Base Code
- **[neuralcode / neural-code](https://github.com/avbiswas/neural-code)** by **AVB (Avik Biswas)** — The original minimal coding agent harness and [Neural Breakdown tutorial](https://youtu.be/Lu1UWqVTbQg). The tutorial's commit-by-commit walkthrough is an exceptional educational resource.

### AI Coding Agent Ecosystem
- **[opencode](https://github.com/opencode-ai/opencode)** (now [charmbracelet/crush](https://github.com/charmbracelet/crush)) — Go-based AI coding agent; architecture reference for efficiency pattern port.
- **[MCP (Model Context Protocol)](https://modelcontextprotocol.io/)** by **Anthropic** — Open protocol for tool exposure to Claude Desktop, Cursor, Windsurf.

### Local LLM Inference Stack
- **[vLLM](https://github.com/vllm-project/vllm)** by **vLLM Team** — High-throughput LLM serving with PagedAttention, continuous batching, prefix caching.
- **[LMCache](https://github.com/LMCache/LMCache)** by **LMCache Team (Yihua Cheng, Yuhan Liu, et al.)** — KV cache management layer for persistent, tiered cache offloading.
- **[Ollama](https://github.com/ollama/ollama)** by **Ollama Team** — Native cross-platform LLM runner with excellent quantization support.
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** by **Georgi Gerganov** — Foundational CPU/GPU inference engine via GGUF.

### Python Ecosystem
- **[PyTorch](https://pytorch.org/)** by **PyTorch Team (Meta AI)** — Tensor computation backbone for vLLM, LMCache.
- **[Rich](https://github.com/Textualize/rich)** by **Textualize (Will McGugan)** — Beautiful terminal formatting, tables, progress bars.
- **[Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)** by **Jonathan Slenders** — Advanced interactive input for the agent REPL.
- **[OpenAI Python SDK](https://github.com/openai/openai-python)** by **OpenAI** — Standard client for OpenAI-compatible APIs.
- **[uv](https://github.com/astral-sh/uv)** by **Astral (Charlie Marsh)** — Fast Python package installer and resolver.

### Infrastructure & Protocols
- **[Hugging Face Hub](https://huggingface.co/)** — Model hosting, versioning, distribution.
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

---

## Disclaimer

This software is provided "as is," without warranty of any kind, express or implied. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability.

- **AI-generated content:** Output from integrated LLMs is generated by AI models. You are solely responsible for how you use, publish, or distribute AI-generated output.
- **Not affiliated:** This project is independent. Not affiliated with, endorsed by, or connected to any model vendor unless explicitly stated.
- **Model licensing:** When downloading models through the smart installer or running local inference, review each model's license before commercial use.

---

*Built with obsessive attention to detail by PyrateGFX Productions.*