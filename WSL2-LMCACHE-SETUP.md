# WSL2 + vLLM + LMCache Setup for Windows

One-command setup for local LLM inference with KV cache offloading on your RTX 5060 Ti.

## Prerequisites

- Windows 10/11 (Build 19041+)
- **NVIDIA GPU drivers installed** (from NVIDIA website or GeForce Experience)
- Admin PowerShell
- ~30GB free disk space

## Quick Start

### 1. Run Setup (Requires Reboot)

```powershell
# Open PowerShell as Administrator
cd C:\Users\Administrator\source\repos\cortex-agent
.\setup-wsl2-lmcache.ps1
```

**This will:**
1. Install WSL2 Ubuntu 24.04
2. Create `.wslconfig` with 24GB RAM / 8GB swap
3. **Prompt you to reboot**

### 2. After Reboot, Run Again

```powershell
.\setup-wsl2-lmcache.ps1 -SkipWSLInstall
```

**This will (inside WSL2):**
1. Update Ubuntu packages
2. Install Python 3.12, CUDA toolkit
3. Create `~/lmcache-env` virtual environment
4. Install PyTorch (CUDA 12.1), vLLM, LMCache
5. Create `~/lmcache_config.yaml` (20GB CPU offload)
6. Create `~/start_vllm.sh` manual launch script
6. Install systemd service `vllm-lmcache`
7. Start service and verify API responds

## What You Get

| Component | Config |
|-----------|--------|
| **Model** | `meta-llama/Llama-3.1-8B-Instruct` (change in script params) |
| **API** | `http://localhost:8000/v1` (OpenAI-compatible) |
| **Context** | 32,768 tokens |
| **GPU Memory** | 85% (13.6GB of 16GB) |
| **LMCache CPU Offload** | 20GB of your 32GB RAM |
| **Auto-start** | systemd service on WSL boot |

## Verify It Works

```powershell
# Test from Windows
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"local-model","messages":[{"role":"user","content":"Hello"}],"max_tokens":10}'
```

## Configure Your Agents

### cortex-agent (`~/.agents/env`)
```bash
BASE_URL=http://localhost:8000/v1
API_KEY=dummy
MODEL=local-model
CONTEXT_WINDOW=32768
```

### opencode (`~/.opencode.json`)
```json
{
  "providers": {
    "local": { "apiKey": "dummy", "baseURL": "http://localhost:8000/v1" }
  },
  "agents": {
    "coder": { "model": "local/local-model" }
  }
}
```

## Management Commands

```powershell
# Service status
wsl -d Ubuntu-24.04 -- sudo systemctl status vllm-lmcache

# Live logs
wsl -d Ubuntu-24.04 -- sudo journalctl -u vllm-lmcache -f

# Restart
wsl -d Ubuntu-24.04 -- sudo systemctl restart vllm-lmcache

# Stop
wsl -d Ubuntu-24.04 -- sudo systemctl stop vllm-lmcache

# Manual run (for debugging)
wsl -d Ubuntu-24.04 -- ~/start_vllm.sh
```

## Customize Model

Edit the script parameters at the top of `setup-wsl2-lmcache.ps1`:

```powershell
[string]$ModelName = "meta-llama/Llama-3.1-8B-Instruct",  # Any HF model
[int]$MaxModelLen = 32768,                                 # Context window
[string]$LMCacheCPUOffloadGB = "20"                        # CPU RAM for KV cache
```

Popular alternatives:
- `microsoft/Phi-3.5-mini-instruct` (smaller, faster)
- `Qwen/Qwen2.5-14B-Instruct` (better coding)
- `codellama/CodeLlama-13b-Instruct-hf` (code specialized)

## Troubleshooting

### "CUDA out of memory"
Reduce `--gpu-memory-utilization` in service file (try 0.80 or 0.75)

### "Model not found"
Model downloads on first run (~16GB for 8B). Check logs:
```powershell
wsl -d Ubuntu-24.04 -- sudo journalctl -u vllm-lmcache -f
```

### Port 8000 in use
Change `$VLLMPort = 8000` in script, or stop conflicting process.

### WSL GPU not detected
```powershell
# In WSL terminal
nvidia-smi
# Should show your RTX 5060 Ti
```

### Slow first request
First request loads model into GPU VRAM. Subsequent requests use LMCache.

## Uninstall

```powershell
wsl --unregister Ubuntu-24.04
Remove-Item "$env:USERPROFILE\.wslconfig" -Force
```