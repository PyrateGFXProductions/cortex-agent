<#
.SYNOPSIS
    Sets up WSL2 Ubuntu with vLLM + LMCache for local LLM inference
.DESCRIPTION
    Installs WSL2 Ubuntu, configures GPU passthrough, installs vLLM + LMCache,
    and creates systemd services for auto-start.
.NOTES
    Requires: Windows 10/11 with admin rights, NVIDIA GPU drivers installed
    Tested on: RTX 5060 Ti (16GB VRAM), 32GB RAM
#>

param(
    [string]$DistroName = "Ubuntu-24.04",
    [int]$MemoryGB = 24,        # RAM for WSL2 (leave 8GB for Windows)
    [int]$SwapGB = 8,           # Swap file size
    [string]$ModelName = "meta-llama/Llama-3.1-8B-Instruct",
    [int]$VLLMPort = 8000,
    [int]$MaxModelLen = 32768,
    [string]$LMCacheCPUOffloadGB = "20"
)

$ErrorActionPreference = "Stop"

function Write-Log($msg, $color = "Cyan") {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor $color
}

function Check-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Log "ERROR: Run PowerShell as Administrator" Red
        exit 1
    }
}

function Check-NVIDIADriver {
    try {
        $driver = nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>$null
        if ($driver) {
            Write-Log "NVIDIA Driver: $driver" Green
            return $true
        }
    } catch {}
    Write-Log "WARNING: nvidia-smi not found. GPU passthrough may not work." Yellow
    return $false
}

function Install-WSL2 {
    Write-Log "Installing WSL2..."
    wsl --install -d $DistroName 2>&1 | ForEach-Object { Write-Host "  $_" }
    
    Write-Log "Setting WSL2 as default..."
    wsl --set-default-version 2
    
    Write-Log "WSL2 installed. You MUST REBOOT now."
    Write-Log "After reboot, run this script again with -SkipWSLInstall"
}

function Configure-WSL2 {
    Write-Log "Configuring WSL2 resources..."
    
    # Create .wslconfig
    $wslConfig = @"
[wsl2]
memory=$("${MemoryGB}GB")
swap=$("${SwapGB}GB")
processors=0  # Use all cores
localhostForwarding=true
"@
    $wslConfigPath = "$env:USERPROFILE\.wslconfig"
    $wslConfig | Out-File -FilePath $wslConfigPath -Encoding utf8
    Write-Log "Created $wslConfigPath"
    
    # Enable systemd in WSL
    $wslConf = @"
[boot]
systemd=true
"@
    wsl -d $DistroName -- bash -c "echo '$wslConf' | sudo tee /etc/wsl.conf > /dev/null"
    Write-Log "Enabled systemd in WSL"
    
    # Restart WSL to apply
    wsl --terminate $DistroName
    Start-Sleep 3
}

function Setup-InsideWSL {
    Write-Log "Running setup inside WSL2..."
    
    $setupScript = @"
set -euo pipefail

echo '=== Updating packages ==='
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

echo '=== Installing dependencies ==='
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget \
    build-essential cmake \
    nvidia-cuda-toolkit

echo '=== Setting up Python venv ==='
python3 -m venv ~/lmcache-env
source ~/lmcache-env/bin/activate

echo '=== Upgrading pip ==='
pip install --upgrade pip setuptools wheel

echo '=== Installing PyTorch (CUDA 12.1) ==='
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo '=== Installing vLLM ==='
pip install vllm

echo '=== Installing LMCache ==='
pip install lmcache

echo '=== Creating LMCache config ==='
cat > ~/lmcache_config.yaml << 'EOFCFG'
lmcache:
  chunk_size: 256
  local_cpu: true
  max_local_cpu_size: $LMCacheCPUOffloadGB
  remote_url: ""
  pipelined_backend: true
  log_level: INFO
EOFCFG

echo '=== Creating vLLM + LMCache launch script ==='
cat > ~/start_vllm.sh << 'EOFSCRIPT'
#!/bin/bash
set -euo pipefail

source ~/lmcache-env/bin/activate

export LMCACHE_CONFIG_FILE=~/lmcache_config.yaml
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

echo 'Starting vLLM with LMCache...'
echo 'Model: $MODEL_NAME'
echo 'Port: $VLLM_PORT'
echo 'Max context: $MAX_MODEL_LEN'
echo 'LMCache CPU offload: $LMCACHE_CPU_OFFLOAD_GB GB'

exec python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_NAME \
    --host 0.0.0.0 \
    --port $VLLM_PORT \
    --gpu-memory-utilization 0.85 \
    --max-model-len $MAX_MODEL_LEN \
    --enable-prefix-caching \
    --disable-log-requests \
    --served-model-name local-model
EOFSCRIPT

chmod +x ~/start_vllm.sh

# Replace placeholders
sed -i "s|\$MODEL_NAME|$ModelName|g" ~/start_vllm.sh
sed -i "s|\$VLLM_PORT|$VLLMPort|g" ~/start_vllm.sh
sed -i "s|\$MAX_MODEL_LEN|$MaxModelLen|g" ~/start_vllm.sh
sed -i "s|\$LMCACHE_CPU_OFFLOAD_GB|$LMCacheCPUOffloadGB|g" ~/start_vllm.sh

echo '=== Creating systemd service ==='
sudo tee /etc/systemd/system/vllm-lmcache.service > /dev/null << 'EOFSERVICE'
[Unit]
Description=vLLM with LMCache
After=network.target nvidia-persistenced.service
Wants=nvidia-persistenced.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER
Environment=PATH=/home/$USER/lmcache-env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=LMCACHE_CONFIG_FILE=/home/$USER/lmcache_config.yaml
Environment=CUDA_VISIBLE_DEVICES=0
Environment=PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
ExecStart=/home/$USER/lmcache-env/bin/python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_NAME \
    --host 0.0.0.0 \
    --port $VLLM_PORT \
    --gpu-memory-utilization 0.85 \
    --max-model-len $MAX_MODEL_LEN \
    --enable-prefix-caching \
    --disable-log-requests \
    --served-model-name local-model
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE

# Replace placeholders in service file
sudo sed -i "s|\$MODEL_NAME|$ModelName|g" /etc/systemd/system/vllm-lmcache.service
sudo sed -i "s|\$VLLM_PORT|$VLLMPort|g" /etc/systemd/system/vllm-lmcache.service
sudo sed -i "s|\$MAX_MODEL_LEN|$MaxModelLen|g" /etc/systemd/system/vllm-lmcache.service
sudo sed -i "s|\$USER|$USER|g" /etc/systemd/system/vllm-lmcache.service

echo '=== Enabling service ==='
sudo systemctl daemon-reload
sudo systemctl enable vllm-lmcache.service

echo '=== Starting service ==='
sudo systemctl start vllm-lmcache.service

echo '=== Waiting for server to be ready ==='
for i in {1..60}; do
    if curl -s http://localhost:$VLLMPORT/v1/models > /dev/null 2>&1; then
        echo 'Server ready!'
        break
    fi
    sleep 2
done

echo '=== Testing ==='
curl -s http://localhost:$VLLMPORT/v1/models | jq .
curl -s -X POST http://localhost:$VLLMPORT/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"local-model","messages":[{"role":"user","content":"Hello"}],"max_tokens":10}' | jq .

echo ''
echo '=== DONE ==='
echo 'vLLM + LMCache running at http://localhost:$VLLMPORT/v1'
echo 'Logs: journalctl -u vllm-lmcache -f'
echo 'Manual start: ~/start_vllm.sh'
"@
    
    # Replace PowerShell variables in the bash script
    $setupScript = $setupScript -replace '\$MODEL_NAME', $ModelName
    $setupScript = $setupScript -replace '\$VLLM_PORT', $VLLMPort
    $setupScript = $setupScript -replace '\$MAX_MODEL_LEN', $MaxModelLen
    $setupScript = $setupScript -replace '\$LMCACHE_CPU_OFFLOAD_GB', $LMCacheCPUOffloadGB
    $setupScript = $setupScript -replace '\$LMCacheCPUOffloadGB', $LMCacheCPUOffloadGB
    $setupScript = $setupScript -replace '\$USER', $env:USERNAME
    
    # Write to temp file and execute in WSL
    $tempPath = "$env:TEMP\wsl-setup.sh"
    $setupScript | Out-File -FilePath $tempPath -Encoding utf8
    
    wsl -d $DistroName -- bash $tempPath
    Remove-Item $tempPath -Force
}

function Test-Connection {
    Write-Log "Testing connection from Windows..."
    Start-Sleep 5
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$VLLMPort/v1/models" -TimeoutSec 10
        Write-Log "SUCCESS: vLLM API responding" Green
        $response | ConvertTo-Json -Depth 3 | ForEach-Object { Write-Host "  $_" }
    } catch {
        Write-Log "WARNING: Could not connect to vLLM. Check WSL logs: journalctl -u vllm-lmcache -f" Yellow
    }
}

# Main
Check-Admin
Check-NVIDIADriver

$skipWSL = $false
if ($args -contains "-SkipWSLInstall") { $skipWSL = $true }

if (-not $skipWSL) {
    Install-WSL2
    Write-Log "REBOOT REQUIRED. Run again with -SkipWSLInstall after reboot." Yellow
    exit 0
}

Configure-WSL2
Setup-InsideWSL
Test-Connection

Write-Log "=== SETUP COMPLETE ===" Green
Write-Log "vLLM + LMCache running at: http://localhost:$VLLMPort/v1"
Write-Log "Model: $ModelName"
Write-Log "Context window: $MaxModelLen tokens"
Write-Log "LMCache CPU offload: $LMCacheCPUOffloadGB GB"
Write-Log ""
Write-Log "Configure your agents:" Cyan
Write-Log "  cortex-agent (~/.agents/env):" Cyan
Write-Log "    BASE_URL=http://localhost:$VLLMPort/v1" Cyan
Write-Log "    API_KEY=dummy" Cyan
Write-Log "    MODEL=local-model" Cyan
Write-Log "    CONTEXT_WINDOW=$MaxModelLen" Cyan
Write-Log "  opencode (~/.opencode.json):" Cyan
Write-Log '    "providers": { "local": { "apiKey": "dummy", "baseURL": "http://localhost:'$VLLMPort'/v1" } }' Cyan
Write-Log '    "agents": { "coder": { "model": "local/local-model" } }' Cyan
Write-Log ""
Write-Log "Manage service:" Cyan
Write-Log "  wsl -d $DistroName -- sudo systemctl status vllm-lmcache" Cyan
Write-Log "  wsl -d $DistroName -- sudo journalctl -u vllm-lmcache -f" Cyan
Write-Log "  wsl -d $DistroName -- sudo systemctl restart vllm-lmcache" Cyan