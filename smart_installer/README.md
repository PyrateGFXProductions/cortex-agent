# Smart LLM Inference Stack Installer

Cross-platform installer that detects your hardware and installs the optimal local LLM inference stack with LMCache integration.

## Quick Start

### Windows (PowerShell)
```powershell
# Run from cortex-agent repo root
.\smart-install.ps1

# Or with options
.\smart-install.ps1 -Model "Qwen/Qwen2.5-14B-Instruct" -Port 8000
.\smart-install.ps1 -DryRun          # Preview what would be installed
.\smart-install.ps1 -CpuOnly         # Force CPU-only mode
```

### Linux/macOS
```bash
# Make executable and run
chmod +x smart-install.sh
./smart-install.sh

# With options
./smart-install.sh --model "meta-llama/Llama-3.1-8B-Instruct" --port 8000
./smart-install.sh --dry-run
./smart-install.sh --cpu-only
```

### Universal (Python)
```bash
python smart_installer/smart_install.py --help
```

## What It Does

1. **Detects Hardware**: GPU (vendor, model, VRAM), CPU, RAM, OS
2. **Selects Optimal Stack**:
   - **NVIDIA GPU (Linux/WSL2)** → vLLM + LMCache (best performance)
   - **Apple Silicon** → Ollama (native, optimized)
   - **AMD/Intel GPU (Linux)** → vLLM + LMCache (ROCm support)
   - **Windows Native (no WSL)** → Ollama or llama.cpp
   - **CPU Only** → llama.cpp with quantization
3. **Installs Dependencies**: PyTorch, vLLM/Ollama/llama.cpp, LMCache
4. **Configures Optimally**: Context window, GPU memory, CPU offload, quantization
5. **Creates Service**: systemd (Linux/WSL2), launchd (macOS), or manual scripts
6. **Outputs Client Configs**: Ready-to-use for cortex-agent, opencode, Continue.dev, etc.

## Hardware Profiles & Recommendations

| Your Hardware | Recommended Stack | Quantization | Context |
|---------------|-------------------|--------------|---------|
| RTX 4090 (24GB) | vLLM + LMCache | FP16 | 128K+ |
| RTX 3080/4080 (10-16GB) | vLLM + LMCache | FP16/8bit | 32-64K |
| RTX 3060/4060 (8-12GB) | vLLM + LMCache | 8bit/4bit | 16-32K |
| MacBook Pro M3 Max (96GB) | Ollama | Q4_K_M | 64K |
| MacBook Air M2 (16GB) | Ollama | Q4_K_M | 16K |
| No GPU (32GB RAM) | llama.cpp | Q4_K_M | 8-16K |

## Installation Output

After installation, you'll have:

```
~/.llm-stack/
├── config/
│   ├── config.yaml          # Main configuration
│   ├── vllm_config.json     # vLLM settings (if applicable)
│   ├── lmcache_config.yaml  # LMCache settings (if applicable)
│   └── ollama_config.json   # Ollama settings (if applicable)
├── start.sh / start.ps1     # Manual launch scripts
├── service/
│   ├── llm-stack.service    # systemd service (Linux/WSL2)
│   └── com.user.llm-stack.plist  # launchd (macOS)
└── client-configs/
    ├── cortex-agent.env     # For cortex-agent
    ├── opencode.json        # For opencode
    ├── generic.json         # Any OpenAI-compatible client
    └── continue.json        # For Continue.dev
```

## Client Integration

### cortex-agent
```bash
# Copy to ~/.agents/env
BASE_URL=http://localhost:8000/v1
API_KEY=dummy
MODEL=local-model
CONTEXT_WINDOW=32768
```

### opencode
```json
// Merge into ~/.opencode.json
{
  "providers": {
    "local": { "apiKey": "dummy", "baseURL": "http://localhost:8000/v1" }
  },
  "agents": {
    "coder": { "model": "local/local-model" }
  }
}
```

### Continue.dev
```json
// ~/.continue/config.json
{
  "models": [{
    "title": "Local Model",
    "provider": "openai",
    "model": "local-model",
    "apiBase": "http://localhost:8000/v1",
    "apiKey": "dummy",
    "contextLength": 32768
  }]
}
```

## Options

| Option | Description |
|--------|-------------|
| `--model MODEL` | HuggingFace model ID or Ollama name (e.g., `Qwen/Qwen2.5-14B-Instruct`, `llama3.1:8b`) |
| `--port PORT` | API port (default: 8000) |
| `--quantization TYPE` | Override: `FP16`, `8bit`, `4bit`, `Q4_K_M`, `Q5_K_M`, `Q8_0` |
| `--cpu-only` | Force CPU-only mode (llama.cpp) |
| `--dry-run` | Show what would be installed without making changes |
| `--force-wsl` | Force WSL2 installation on Windows |

## Platform-Specific Notes

### Windows
- **vLLM requires WSL2** — installer will prompt to install WSL2 Ubuntu if not present
- **Ollama** — native Windows install, no WSL needed
- **GPU passthrough** — requires NVIDIA drivers on host

### Linux
- **NVIDIA** — install drivers first (`nvidia-driver-550` or newer)
- **AMD** — install ROCm (`rocm-6.0` or newer)
- **systemd service** — auto-starts on boot

### macOS
- **Apple Silicon only** — Intel Macs fall back to CPU mode
- **Homebrew required** — for Ollama install
- **launchd service** — auto-starts on login

## Troubleshooting

### "CUDA out of memory"
Reduce `gpu_memory_utilization` in config (try 0.8 or 0.75)

### Model not found / download fails
Check internet connection. Models download on first run (8B ~16GB, 70B ~40GB)

### Port already in use
Change port: `--port 8001`

### WSL2 not found (Windows)
```powershell
wsl --install -d Ubuntu-24.04
# Reboot, then re-run installer
```

### Slow first request
First request loads model into GPU. Subsequent requests use LMCache/Ollama cache.

## Uninstall

```bash
# Linux/macOS
sudo systemctl stop llm-stack && sudo systemctl disable llm-stack
rm -rf ~/.llm-stack

# Windows (if using WSL2)
wsl --unregister Ubuntu-24.04
rm -rf ~/.llm-stack
```

## License

MIT — Part of cortex-agent efficiency patterns