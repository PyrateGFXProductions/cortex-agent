#!/usr/bin/env python3
"""
Smart LLM Inference Stack Installer - Interactive Version
Detects hardware, presents options, and installs with full user control.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from hardware_detect import detect_hardware, get_hardware_profile, HardwareInfo
from interactive import InteractiveInstaller


class SmartInstaller:
    def __init__(self, args, ui: InteractiveInstaller):
        self.args = args
        self.ui = ui
        self.hw: Optional[HardwareInfo] = None
        self.profile: Dict[str, Any] = {}
        self.selected_stack: str = ""
        self.selected_options: Dict[str, bool] = {}
        self.selected_model: str = ""
        self.install_dir = Path.home() / ".llm-stack"
        self.dry_run = args.dry_run
        self.venv_path = self.install_dir / "venv"

    def log(self, msg: str, level: str = "info"):
        """Log via UI."""
        getattr(self.ui, f"show_{level}")(msg)

    def run_cmd(self, cmd: list, cwd: Optional[Path] = None, check: bool = True, env: Dict = None) -> subprocess.CompletedProcess:
        """Run command with dry-run support."""
        if self.dry_run:
            self.ui.show_progress(f"DRY RUN: {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        self.ui.show_progress(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env or os.environ.copy())
        if check and result.returncode != 0:
            self.ui.show_error(f"Command failed: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result

    def detect(self):
        """Detect hardware and profile."""
        self.ui.show_progress("Detecting hardware...")
        self.hw = detect_hardware()
        self.profile = get_hardware_profile(self.hw)

        # Show hardware summary and confirm
        if not self.ui.show_hardware_summary(self.hw, self.profile):
            self.ui.show_error("Hardware detection cancelled. Exiting.")
            sys.exit(1)

    def select_stack(self):
        """Interactive stack selection."""
        self.selected_options = self.ui.show_stack_options(self.profile, self.hw)
        self.selected_stack = [k for k, v in self.selected_options.items() if v][0]

        # If vLLM selected on Windows without WSL, prompt for WSL
        if self.selected_stack == "vllm_lmcache" and self.hw.os == "Windows" and not self.hw.platform_details.get("wsl"):
            if not self.ui.prompt_wsl_install():
                self.ui.show_warning("WSL2 required for vLLM. Falling back to Ollama.")
                self.selected_stack = "ollama"
                self.selected_options = {k: (k == "ollama") for k in self.selected_options}

    def select_additional_options(self):
        """Interactive additional options selection."""
        additional = self.ui.show_additional_options(self.selected_stack, self.hw)
        self.selected_options.update(additional)

        # Auto-enable dependencies
        if self.selected_stack == "vllm_lmcache":
            if self.hw.gpu and self.hw.gpu.vendor == 'nvidia':
                self.selected_options["cuda_toolkit"] = True
                self.selected_options["python_venv"] = True
            elif self.hw.gpu and self.hw.gpu.vendor == 'amd':
                self.selected_options["rocm"] = True
                self.selected_options["python_venv"] = True
        if self.selected_stack in ("vllm_lmcache", "llama_cpp"):
            self.selected_options["python_venv"] = True

    def select_model(self):
        """Interactive model selection."""
        self.selected_model = self.ui.show_model_selection(self.selected_stack, self.profile, self.hw)

    def check_prerequisites(self) -> bool:
        """Check and display missing prerequisites."""
        missing = self.ui.check_prerequisites(self.hw, self.selected_options)
        if missing:
            self.ui.print_header("MISSING PREREQUISITES", "The following are required but not detected:")
            for m in missing:
                self.ui.show_warning(m)
            return self.ui.confirm("Continue anyway? (Install may fail)", default=False)
        return True

    def show_install_plan(self):
        """Show complete installation plan."""
        self.ui.print_header("INSTALLATION PLAN", "Review before proceeding")

        # Stack
        self.ui.print_info(f"Primary Stack: {self.selected_stack}", "info")
        self.ui.print_info(f"Model: {self.selected_model}", "info")

        # Options
        enabled = [k for k, v in self.selected_options.items() if v]
        if enabled:
            self.ui.print_info("Additional Components:", "info")
            for opt in enabled:
                opt_info = self.ui.options.get(opt)
                if opt_info:
                    self.ui.print_info(f"  • {opt_info.name} ({opt_info.size_mb} MB)", "dim")

        # Install directory
        self.ui.print_info(f"Install Directory: {self.install_dir}", "info")

        # Disk space check
        try:
            stat = shutil.disk_usage(self.install_dir.parent)
            available_gb = stat.free / (1024**3)
            self.ui.print_info(f"Available Disk Space: {available_gb:.1f} GB", "info")
        except Exception:
            pass

        # Confirm
        if not self.ui.confirm("\nProceed with installation?", default=True):
            self.ui.show_error("Installation cancelled by user.")
            sys.exit(0)

    def create_dirs(self):
        """Create directory structure."""
        dirs = [
            self.install_dir,
            self.install_dir / "config",
            self.install_dir / "models",
            self.install_dir / "logs",
            self.install_dir / "service",
            self.install_dir / "client-configs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self.ui.show_success(f"Created directories at {self.install_dir}")

    def create_venv(self):
        """Create Python virtual environment."""
        self.ui.show_progress("Creating Python virtual environment...")
        if self.dry_run:
            return
        self.run_cmd([sys.executable, "-m", "venv", str(self.venv_path)])
        # Upgrade pip
        pip = self.venv_path / "bin" / "pip"
        if platform.system() == "Windows":
            pip = self.venv_path / "Scripts" / "pip.exe"
        self.run_cmd([str(pip), "install", "--upgrade", "pip", "setuptools", "wheel"])
        self.ui.show_success("Virtual environment ready")

    def get_python(self) -> str:
        """Get venv python path."""
        if platform.system() == "Windows":
            return str(self.venv_path / "Scripts" / "python.exe")
        return str(self.venv_path / "bin" / "python")

    def get_pip(self) -> str:
        """Get venv pip path."""
        if platform.system() == "Windows":
            return str(self.venv_path / "Scripts" / "pip.exe")
        return str(self.venv_path / "bin" / "pip")

    def install_cuda_toolkit(self):
        """Install NVIDIA CUDA Toolkit (Linux/WSL2)."""
        self.ui.show_progress("Installing NVIDIA CUDA Toolkit...")
        if self.dry_run:
            return
        if platform.system() == "Linux":
            # Add NVIDIA repo and install
            self.run_cmd(["wget", "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404.pin"])
            self.run_cmd(["sudo", "mv", "cuda-ubuntu2404.pin", "/etc/apt/preferences.d/cuda-repository-pin-600"])
            self.run_cmd(["wget", "https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda-repo-ubuntu2404-12-1-local_12.1.0-530.30.02-1_amd64.deb"])
            self.run_cmd(["sudo", "dpkg", "-i", "cuda-repo-ubuntu2404-12-1-local_12.1.0-530.30.02-1_amd64.deb"])
            self.run_cmd(["sudo", "cp", "/var/cuda-repo-ubuntu2404-12-1-local/cuda-*-keyring.gpg", "/usr/share/keyrings/"])
            self.run_cmd(["sudo", "apt-get", "update"])
            self.run_cmd(["sudo", "apt-get", "install", "-y", "cuda-toolkit-12-1"])
        elif platform.system() == "Windows":
            self.ui.show_warning("CUDA Toolkit on Windows: Download from https://developer.nvidia.com/cuda-toolkit")
        self.ui.show_success("CUDA Toolkit installation initiated")

    def install_rocm(self):
        """Install AMD ROCm (Linux)."""
        self.ui.show_progress("Installing AMD ROCm...")
        if self.dry_run:
            return
        if platform.system() == "Linux":
            self.run_cmd(["wget", "https://repo.radeon.com/rocm/rocm.gpg.key", "-O", "-"], check=False)
            # Simplified - full ROCm install is complex
            self.ui.show_warning("ROCm installation is complex. See https://rocm.docs.amd.com/en/latest/install/install.html")
        self.ui.show_success("ROCm installation initiated")

    def install_vllm_lmcache(self):
        """Install vLLM + LMCache."""
        py = self.get_python()
        pip = self.get_pip()

        self.ui.show_progress("Installing PyTorch (CUDA 12.1)...")
        if not self.dry_run:
            self.run_cmd([pip, "install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu121"])

        self.ui.show_progress("Installing vLLM...")
        if not self.dry_run:
            self.run_cmd([pip, "install", "vllm"])

        self.ui.show_progress("Installing LMCache...")
        if not self.dry_run:
            self.run_cmd([pip, "install", "lmcache"])

        self.ui.show_success("vLLM + LMCache installed")

    def install_ollama(self):
        """Install Ollama."""
        self.ui.show_progress("Installing Ollama...")
        if self.dry_run:
            return

        system = platform.system()
        if system == "Darwin":
            if shutil.which("brew"):
                self.run_cmd(["brew", "install", "ollama"])
            else:
                self.ui.show_error("Homebrew required. Install from https://brew.sh")
                return False
        elif system == "Windows":
            import urllib.request
            url = "https://ollama.com/download/OllamaSetup.exe"
            installer = self.install_dir / "OllamaSetup.exe"
            self.run_cmd(["curl", "-L", url, "-o", str(installer)], check=False)
            if installer.exists():
                self.run_cmd([str(installer), "/S"])
        elif system == "Linux":
            self.run_cmd(["sh", "-c", "$(curl -fsSL https://ollama.com/install.sh)"])
        self.ui.show_success("Ollama installed")
        return True

    def install_llama_cpp(self):
        """Install llama.cpp."""
        py = self.get_python()
        pip = self.get_pip()
        self.ui.show_progress("Installing llama.cpp...")
        if not self.dry_run:
            self.run_cmd([pip, "install", "llama-cpp-python"])
        self.ui.show_success("llama.cpp installed")
        return True

    def generate_vllm_config(self) -> Dict[str, Any]:
        cpu_offload = self.profile.get("cpu_offload_gb", 0)
        gpu_util = self.profile.get("gpu_memory_utilization", 0.85)
        context = self.profile.get("context_window", 32768)
        model = self.selected_model

        return {
            "vllm": {
                "model": model,
                "host": "0.0.0.0",
                "port": self.args.port,
                "gpu_memory_utilization": gpu_util,
                "max_model_len": context,
                "enable_prefix_caching": True,
                "disable_log_requests": True,
                "served_model_name": "local-model",
                "dtype": "auto" if self.profile["quantization"] == "FP16" else "half",
            },
            "lmcache": {
                "chunk_size": 256,
                "local_cpu": True,
                "max_local_cpu_size": cpu_offload,
                "remote_url": "",
                "pipelined_backend": True,
                "log_level": "INFO",
            }
        }

    def generate_ollama_config(self) -> Dict[str, Any]:
        model = self.selected_model
        ollama_models = {
            "meta-llama/Llama-3.1-8B-Instruct": "llama3.1:8b",
            "meta-llama/Llama-3.1-70B-Instruct": "llama3.1:70b",
            "Qwen/Qwen2.5-7B-Instruct": "qwen2.5:7b",
            "Qwen/Qwen2.5-14B-Instruct": "qwen2.5:14b",
            "Qwen/Qwen2.5-32B-Instruct": "qwen2.5:32b",
            "codellama/CodeLlama-13b-Instruct-hf": "codellama:13b",
            "codellama/CodeLlama-34b-Instruct-hf": "codellama:34b",
            "microsoft/Phi-3.5-mini-instruct": "phi3.5:3.8b",
            "google/gemma-2-2b-it": "gemma2:2b",
            "google/gemma-2-9b-it": "gemma2:9b",
        }
        model = ollama_models.get(model, model.split("/")[-1].lower())
        return {
            "ollama": {
                "model": model,
                "host": "0.0.0.0",
                "port": self.args.port,
                "num_ctx": self.profile.get("context_window", 32768),
                "num_gpu": -1 if self.hw.gpu and not self.hw.gpu.unified_memory else 0,
            }
        }

    def generate_llama_cpp_config(self) -> Dict[str, Any]:
        return {
            "llama_cpp": {
                "model": self.selected_model,
                "host": "0.0.0.0",
                "port": self.args.port,
                "n_ctx": self.profile.get("context_window", 8192),
                "n_gpu_layers": -1 if self.hw.gpu and not self.hw.gpu.unified_memory else 0,
                "n_threads": self.hw.cpu.threads,
                "use_mmap": True,
                "use_mlock": False,
            }
        }

    def write_configs(self):
        """Write configuration files."""
        self.ui.show_progress("Generating configuration files...")

        if self.selected_stack == "vllm_lmcache":
            config = self.generate_vllm_config()
            (self.install_dir / "config" / "vllm_config.json").write_text(json.dumps(config["vllm"], indent=2))
            (self.install_dir / "config" / "lmcache_config.yaml").write_text(self._dict_to_yaml(config["lmcache"]))
        elif self.selected_stack == "ollama":
            config = self.generate_ollama_config()
            (self.install_dir / "config" / "ollama_config.json").write_text(json.dumps(config["ollama"], indent=2))
        else:
            config = self.generate_llama_cpp_config()
            (self.install_dir / "config" / "llama_cpp_config.json").write_text(json.dumps(config["llama_cpp"], indent=2))

        # Main config
        main_config = {
            "stack": self.selected_stack,
            "profile": self.profile["name"],
            "model": self.selected_model,
            "port": self.args.port,
            "api_base": f"http://localhost:{self.args.port}/v1",
        }
        (self.install_dir / "config" / "config.yaml").write_text(self._dict_to_yaml(main_config))

        # Hardware info
        import dataclasses
        (self.install_dir / "hardware.json").write_text(json.dumps({
            "hardware": dataclasses.asdict(self.hw),
            "profile": self.profile,
            "selected": {k: v for k, v in self.selected_options.items() if v},
            "model": self.selected_model
        }, indent=2, default=str))

        self.ui.show_success("Configuration files written")

    def _dict_to_yaml(self, data: Dict) -> str:
        def convert(obj, indent=0):
            lines = []
            for k, v in obj.items():
                prefix = "  " * indent
                if isinstance(v, dict):
                    lines.append(f"{prefix}{k}:")
                    lines.append(convert(v, indent + 1))
                elif isinstance(v, bool):
                    lines.append(f"{prefix}{k}: {str(v).lower()}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{prefix}{k}: {v}")
                elif v is None:
                    lines.append(f"{prefix}{k}: null")
                else:
                    lines.append(f'{prefix}{k}: "{v}"')
            return "\n".join(lines)
        return convert(data)

    def create_launch_scripts(self):
        """Create manual launch scripts."""
        port = self.args.port
        model = self.selected_model

        if self.selected_stack == "vllm_lmcache":
            cpu_offload = self.profile.get("cpu_offload_gb", 20)
            gpu_util = self.profile.get("gpu_memory_utilization", 0.85)
            context = self.profile.get("context_window", 32768)

            sh = f"""#!/bin/bash
# vLLM + LMCache manual launch
set -euo pipefail
export LMCACHE_CONFIG_FILE={self.install_dir}/config/lmcache_config.yaml
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
echo "Starting vLLM + LMCache..."
echo "Model: {model} | Port: {port} | Context: {context} | CPU Offload: {cpu_offload} GB"
exec {self.get_python()} -m vllm.entrypoints.openai.api_server \\
    --model {model} --host 0.0.0.0 --port {port} \\
    --gpu-memory-utilization {gpu_util} --max-model-len {context} \\
    --enable-prefix-caching --disable-log-requests --served-model-name local-model
"""
            ps = f"""# vLLM + LMCache manual launch (PowerShell)
$env:LMCACHE_CONFIG_FILE = "{self.install_dir}/config/lmcache_config.yaml"
$env:CUDA_VISIBLE_DEVICES = "0"
$env:PYTORCH_CUDA_ALLOC_CONF = "max_split_size_mb:128"
Write-Host "Starting vLLM + LMCache..."
Write-Host "Model: {model} | Port: {port} | Context: {context} | CPU Offload: {cpu_offload} GB"
& "{self.get_python()}" -m vllm.entrypoints.openai.api_server `
    --model {model} --host 0.0.0.0 --port {port} `
    --gpu-memory-utilization {gpu_util} --max-model-len {context} `
    --enable-prefix-caching --disable-log-requests --served-model-name local-model
"""

        elif self.selected_stack == "ollama":
            sh = f"""#!/bin/bash
echo "Starting Ollama with {model}..."
ollama serve &
sleep 3
ollama run {model}
"""
            ps = f"""# Ollama manual launch
Write-Host "Starting Ollama with {model}..."
Start-Process ollama -ArgumentList "serve"
Start-Sleep 3
ollama run {model}
"""

        else:  # llama_cpp
            sh = f"""#!/bin/bash
echo "Starting llama.cpp server with {model}..."
{self.get_python()} -m llama_cpp.server \\
    --model {model} --host 0.0.0.0 --port {port} \\
    --n_ctx {self.profile.get('context_window', 8192)} \\
    --n_gpu_layers -1 --n_threads {self.hw.cpu.threads}
"""
            ps = f"""# llama.cpp server manual launch
Write-Host "Starting llama.cpp server with {model}..."
& "{self.get_python()}" -m llama_cpp.server `
    --model {model} --host 0.0.0.0 --port {port} `
    --n_ctx {self.profile.get('context_window', 8192)} `
    --n_gpu_layers -1 --n_threads {self.hw.cpu.threads}
"""

        (self.install_dir / "start.sh").write_text(sh)
        (self.install_dir / "start.sh").chmod(0o755)
        (self.install_dir / "start.ps1").write_text(ps)
        self.ui.show_success("Launch scripts created")

    def create_service(self):
        """Create system service."""
        self.ui.show_progress("Creating system service...")
        stack = self.selected_stack
        port = self.args.port
        model = self.selected_model
        system = platform.system()

        if system == "Linux" or (system == "Windows" and self.hw.platform_details.get("wsl")):
            if stack == "vllm_lmcache":
                cpu_offload = self.profile.get("cpu_offload_gb", 20)
                gpu_util = self.profile.get("gpu_memory_utilization", 0.85)
                context = self.profile.get("context_window", 32768)
                service = f"""[Unit]
Description=vLLM with LMCache
After=network.target nvidia-persistenced.service
Wants=nvidia-persistenced.service

[Service]
Type=simple
User={os.getenv('USER', 'ubuntu')}
WorkingDirectory={self.install_dir}
Environment=PATH={self.venv_path}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=LMCACHE_CONFIG_FILE={self.install_dir}/config/lmcache_config.yaml
Environment=CUDA_VISIBLE_DEVICES=0
Environment=PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
ExecStart={self.get_python()} -m vllm.entrypoints.openai.api_server \\
    --model {model} --host 0.0.0.0 --port {port} \\
    --gpu-memory-utilization {gpu_util} --max-model-len {context} \\
    --enable-prefix-caching --disable-log-requests --served-model-name local-model
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
            elif stack == "ollama":
                service = f"""[Unit]
Description=Ollama Server
After=network.target
[Service]
Type=simple
User={os.getenv('USER', 'ubuntu')}
ExecStart=/usr/local/bin/ollama serve
Environment=OLLAMA_HOST=0.0.0.0:{port}
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
"""
            else:
                service = f"""[Unit]
Description=llama.cpp Server
After=network.target
[Service]
Type=simple
User={os.getenv('USER', 'ubuntu')}
WorkingDirectory={self.install_dir}
ExecStart={self.get_python()} -m llama_cpp.server --model {model} --host 0.0.0.0 --port {port} --n_ctx {self.profile.get('context_window', 8192)}
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
"""
            (self.install_dir / "service" / "llm-stack.service").write_text(service)
            self.ui.show_success("Systemd service created")

        elif system == "Darwin":
            # launchd plist
            if stack == "ollama":
                plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.user.llm-stack.ollama</string>
    <key>ProgramArguments</key><array><string>/opt/homebrew/bin/ollama</string><string>serve</string></array>
    <key>EnvironmentVariables</key><dict><key>OLLAMA_HOST</key><string>0.0.0.0:{port}</string></dict>
    <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{self.install_dir}/logs/ollama.log</string>
    <key>StandardErrorPath</key><string>{self.install_dir}/logs/ollama.error.log</string>
</dict></plist>"""
            else:
                plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.user.llm-stack.llama-cpp</string>
    <key>ProgramArguments</key><array><string>{self.get_python()}</string><string>-m</string><string>llama_cpp.server</string><string>--model</string><string>{model}</string><string>--host</string><string>0.0.0.0</string><string>--port</string><string>{port}</string></array>
    <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
    <key>WorkingDirectory</key><string>{self.install_dir}</string>
    <key>StandardOutPath</key><string>{self.install_dir}/logs/llama-cpp.log</string>
    <key>StandardErrorPath</key><string>{self.install_dir}/logs/llama-cpp.error.log</string>
</dict></plist>"""
            (self.install_dir / "service" / "com.user.llm-stack.plist").write_text(plist)
            self.ui.show_success("Launchd plist created")

        elif system == "Windows":
            self.ui.show_warning("Windows native service: Use Task Scheduler or run start.ps1 manually")

    def generate_client_configs(self) -> Dict[str, str]:
        """Generate client configuration files."""
        port = self.args.port
        base_url = f"http://localhost:{port}/v1"

        client_configs = {}

        # cortex-agent
        cortex_env = f"""BASE_URL={base_url}
API_KEY=dummy
MODEL=local-model
CONTEXT_WINDOW={self.profile.get('context_window', 32768)}
"""
        (self.install_dir / "client-configs" / "cortex-agent.env").write_text(cortex_env)
        client_configs["cortex-agent"] = str(self.install_dir / "client-configs" / "cortex-agent.env")

        # opencode
        opencode_config = {
            "providers": {"local": {"apiKey": "dummy", "baseURL": base_url}},
            "agents": {"coder": {"model": "local/local-model"}, "task": {"model": "local/local-model"}, "summarizer": {"model": "local/local-model"}}
        }
        (self.install_dir / "client-configs" / "opencode.json").write_text(json.dumps(opencode_config, indent=2))
        client_configs["opencode"] = str(self.install_dir / "client-configs" / "opencode.json")

        # generic
        generic = {"base_url": base_url, "api_key": "dummy", "model": "local-model", "max_tokens": self.profile.get("context_window", 32768)}
        (self.install_dir / "client-configs" / "generic.json").write_text(json.dumps(generic, indent=2))
        client_configs["generic"] = str(self.install_dir / "client-configs" / "generic.json")

        # Continue.dev
        continue_config = {"models": [{"title": "Local Model", "provider": "openai", "model": "local-model", "apiBase": base_url, "apiKey": "dummy", "contextLength": self.profile.get("context_window", 32768)}], "tabAutocompleteModel": {"title": "Local Model", "provider": "openai", "model": "local-model", "apiBase": base_url, "apiKey": "dummy"}}
        (self.install_dir / "client-configs" / "continue.json").write_text(json.dumps(continue_config, indent=2))
        client_configs["continue.dev"] = str(self.install_dir / "client-configs" / "continue.json")

        self.ui.show_success("Client configurations generated")
        return client_configs

    def pre_download_model(self):
        """Pre-download model if requested."""
        if not self.selected_options.get("models"):
            return

        self.ui.show_progress(f"Pre-downloading model: {self.selected_model}...")
        if self.dry_run:
            return

        if self.selected_stack == "ollama":
            # Convert HF to Ollama name
            ollama_models = {
                "meta-llama/Llama-3.1-8B-Instruct": "llama3.1:8b",
                "meta-llama/Llama-3.1-70B-Instruct": "llama3.1:70b",
                "Qwen/Qwen2.5-7B-Instruct": "qwen2.5:7b",
                "Qwen/Qwen2.5-14B-Instruct": "qwen2.5:14b",
                "Qwen/Qwen2.5-32B-Instruct": "qwen2.5:32b",
                "codellama/CodeLlama-13b-Instruct-hf": "codellama:13b",
                "codellama/CodeLlama-34b-Instruct-hf": "codellama:34b",
                "microsoft/Phi-3.5-mini-instruct": "phi3.5:3.8b",
                "google/gemma-2-2b-it": "gemma2:2b",
                "google/gemma-2-9b-it": "gemma2:9b",
            }
            model = ollama_models.get(self.selected_model, self.selected_model.split("/")[-1].lower())
            self.run_cmd(["ollama", "pull", model], check=False)
        elif self.selected_stack == "vllm_lmcache":
            # vLLM downloads on first request; we can trigger a dummy request
            self.ui.show_info("vLLM downloads model on first request. Starting server briefly...")
            # Could start server, make request, stop - complex for now
            self.ui.show_warning("Model will download on first API request to vLLM")

        self.ui.show_success("Model download initiated")

    def run(self):
        """Main interactive installation flow."""
        self.ui.print_header("SMART LLM INFERENCE STACK INSTALLER", "Interactive • Hardware-Aware • User-Controlled")

        if self.dry_run:
            self.ui.show_warning("DRY RUN MODE - No changes will be made")

        # Step 1: Detect hardware
        self.detect()

        # Step 2: Select stack
        self.select_stack()

        # Step 3: Additional options
        self.select_additional_options()

        # Step 4: Select model
        self.select_model()

        # Step 5: Check prerequisites
        if not self.check_prerequisites():
            return 1

        # Step 6: Show plan and confirm
        self.show_install_plan()

        # Step 7: Install
        self.create_dirs()

        # Install components in order
        if self.selected_options.get("python_venv"):
            self.create_venv()

        if self.selected_options.get("cuda_toolkit"):
            self.install_cuda_toolkit()

        if self.selected_options.get("rocm"):
            self.install_rocm()

        if self.selected_stack == "vllm_lmcache":
            self.install_vllm_lmcache()
        elif self.selected_stack == "ollama":
            self.install_ollama()
        elif self.selected_stack == "llama_cpp":
            self.install_llama_cpp()

        # Post-install config
        self.write_configs()
        self.create_launch_scripts()

        if self.selected_options.get("systemd_service") or self.selected_options.get("launchd_service") or self.selected_options.get("task_scheduler"):
            self.create_service()

        client_configs = self.generate_client_configs()

        if self.selected_options.get("models"):
            self.pre_download_model()

        # Step 8: Show completion
        self.ui.show_post_install(self.install_dir, self.selected_model, self.selected_stack, self.args.port, client_configs)

        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Smart LLM Inference Stack Installer (Interactive)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python smart_installer/smart_install.py           # Full interactive mode
          python smart_installer/smart_install.py --dry-run # Preview what would happen
          python smart_installer/smart_install.py --port 8000
        """)
    )
    parser.add_argument("--model", help="Model to install (skips model selection prompt)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without installing")
    parser.add_argument("--no-rich", action="store_true", help="Disable rich UI (use plain text)")

    args = parser.parse_args()

    ui = InteractiveInstaller(use_rich=not args.no_rich)

    # Pre-set model if provided
    if args.model:
        # We'll handle this in select_model
        pass

    installer = SmartInstaller(args, ui)
    return installer.run()


if __name__ == "__main__":
    sys.exit(main())