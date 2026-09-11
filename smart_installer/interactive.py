#!/usr/bin/env python3
"""
Interactive installer UI - handles all user prompts, confirmations, and information display.
"""

import sys
import textwrap
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.text import Text
    from rich.columns import Columns
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Colors:
    """ANSI color codes for non-rich fallback."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    DIM = '\033[2m'


@dataclass
class InstallOption:
    """Represents an installable component with metadata."""
    id: str
    name: str
    description: str
    requires: List[str]  # Other option IDs this depends on
    conflicts: List[str]  # Other option IDs this conflicts with
    size_mb: int
    recommended_for: List[str]  # Hardware profiles
    default: bool = False


class InteractiveInstaller:
    """Handles all user interaction for the smart installer."""

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and RICH_AVAILABLE
        if self.use_rich:
            self.console = Console()
        self.options = self._define_options()

    def _define_options(self) -> Dict[str, InstallOption]:
        """Define all installable components."""
        return {
            "wsl2": InstallOption(
                id="wsl2",
                name="WSL2 (Windows Subsystem for Linux)",
                description="Required for vLLM on Windows. Installs Ubuntu 24.04 with GPU passthrough.",
                requires=[],
                conflicts=[],
                size_mb=2000,
                recommended_for=["windows"],
                default=False
            ),
            "vllm": InstallOption(
                id="vllm",
                name="vLLM Inference Server",
                description="High-performance LLM serving engine with PagedAttention, continuous batching, and prefix caching.",
                requires=["python3.10+", "cuda"],
                conflicts=["ollama", "llama.cpp"],
                size_mb=3000,
                recommended_for=["nvidia_gpu_8gb+", "amd_gpu_8gb+"],
                default=False
            ),
            "lmcache": InstallOption(
                id="lmcache",
                name="LMCache KV Cache Layer",
                description="Persistent KV cache offloading to CPU RAM/disk. Reduces TTFT for repeated prompts. Works with vLLM.",
                requires=["vllm"],
                conflicts=[],
                size_mb=500,
                recommended_for=["nvidia_gpu_8gb+"],
                default=False
            ),
            "ollama": InstallOption(
                id="ollama",
                name="Ollama",
                description="Native LLM runner with simple CLI. Supports macOS, Linux, Windows. Good quantization support.",
                requires=[],
                conflicts=["vllm", "llama.cpp"],
                size_mb=800,
                recommended_for=["apple_silicon", "windows_native", "linux_no_cuda"],
                default=False
            ),
            "llama_cpp": InstallOption(
                id="llama_cpp",
                name="llama.cpp Server",
                description="CPU/GPU inference via GGUF models. Most flexible for CPU-only or older GPUs.",
                requires=["python3.8+"],
                conflicts=["vllm", "ollama"],
                size_mb=200,
                recommended_for=["cpu_only", "low_vram"],
                default=False
            ),
            "cuda_toolkit": InstallOption(
                id="cuda_toolkit",
                name="NVIDIA CUDA Toolkit",
                description="Required for vLLM + LMCache on NVIDIA GPUs. Includes nvcc, cuDNN, drivers.",
                requires=["nvidia_driver"],
                conflicts=[],
                size_mb=4000,
                recommended_for=["nvidia_gpu"],
                default=False
            ),
            "rocm": InstallOption(
                id="rocm",
                name="AMD ROCm",
                description="Required for vLLM on AMD GPUs. Includes HIP, MIOpen.",
                requires=["amd_gpu"],
                conflicts=[],
                size_mb=3000,
                recommended_for=["amd_gpu_8gb+"],
                default=False
            ),
            "python_venv": InstallOption(
                id="python_venv",
                name="Python Virtual Environment",
                description="Isolated Python environment for vLLM/LMCache/llama.cpp dependencies.",
                requires=["python3.10+"],
                conflicts=[],
                size_mb=100,
                recommended_for=["vllm", "llama_cpp"],
                default=False
            ),
            "models": InstallOption(
                id="models",
                name="Pre-download Models",
                description="Download selected models during install (avoids first-request delay).",
                requires=["vllm", "ollama", "llama_cpp"],
                conflicts=[],
                size_mb=0,  # Variable
                recommended_for=["all"],
                default=False
            ),
            "systemd_service": InstallOption(
                id="systemd_service",
                name="Systemd Service (Auto-start)",
                description="Create systemd service for auto-start on boot (Linux/WSL2).",
                requires=["vllm", "ollama", "llama_cpp"],
                conflicts=[],
                size_mb=0,
                recommended_for=["linux", "wsl2"],
                default=False
            ),
            "launchd_service": InstallOption(
                id="launchd_service",
                name="Launchd Service (Auto-start macOS)",
                description="Create launchd plist for auto-start on login (macOS).",
                requires=["ollama", "llama_cpp"],
                conflicts=[],
                size_mb=0,
                recommended_for=["macos"],
                default=False
            ),
            "task_scheduler": InstallOption(
                id="task_scheduler",
                name="Task Scheduler (Auto-start Windows)",
                description="Create Windows Task Scheduler entry for auto-start on login.",
                requires=["ollama", "llama_cpp"],
                conflicts=[],
                size_mb=0,
                recommended_for=["windows_native"],
                default=False
            ),
        }

    def print_header(self, title: str, subtitle: str = ""):
        """Print a styled header."""
        if self.use_rich:
            self.console.print()
            self.console.rule(f"[bold cyan]{title}[/bold cyan]")
            if subtitle:
                self.console.print(f"[dim]{subtitle}[/dim]")
            self.console.print()
        else:
            print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
            print(f"{Colors.CYAN}{Colors.BOLD}{title:^60}{Colors.RESET}")
            if subtitle:
                print(f"{Colors.DIM}{subtitle:^60}{Colors.RESET}")
            print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    def print_info(self, message: str, style: str = "info"):
        """Print informational message."""
        if self.use_rich:
            styles = {"info": "cyan", "success": "green", "warn": "yellow", "error": "red", "dim": "dim"}
            self.console.print(f"[{styles.get(style, 'white')}]>> {message}[/{styles.get(style, 'white')}]")
        else:
            prefix = {"info": ">>", "success": "OK", "warn": "WARNING", "error": "ERROR"}
            color = {"info": Colors.CYAN, "success": Colors.GREEN, "warn": Colors.YELLOW, "error": Colors.RED}
            print(f"{color.get(style, Colors.RESET)}{prefix.get(style, '>>')} {message}{Colors.RESET}")

    def print_table(self, title: str, columns: List[str], rows: List[List[str]], styles: List[str] = None):
        """Print a formatted table."""
        if self.use_rich:
            table = Table(title=title, show_header=True, header_style="bold cyan")
            for i, col in enumerate(columns):
                table.add_column(col, style=styles[i] if styles else None)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)
        else:
            # Simple text table
            col_widths = [max(len(str(c)) for c in col) for col in zip(columns, *rows)]
            header = " | ".join(c.ljust(w) for c, w in zip(columns, col_widths))
            print(f"\n{Colors.BOLD}{header}{Colors.RESET}")
            print("-" * len(header))
            for row in rows:
                print(" | ".join(str(c).ljust(w) for c, w in zip(row, col_widths)))

    def confirm(self, message: str, default: bool = True) -> bool:
        """Ask yes/no question."""
        if self.use_rich:
            return Confirm.ask(f"[cyan]{message}[/cyan]", default=default)
        else:
            suffix = " [Y/n]" if default else " [y/N]"
            while True:
                resp = input(f"{Colors.CYAN}{message}{suffix} {Colors.RESET}").strip().lower()
                if not resp:
                    return default
                if resp in ('y', 'yes'):
                    return True
                if resp in ('n', 'no'):
                    return False
                print("Please enter 'y' or 'n'")

    def select_one(self, message: str, choices: List[Tuple[str, str]], default: str = None) -> str:
        """Select one option from list. choices = [(id, description), ...]"""
        if self.use_rich:
            # Build table for display
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Option", style="bold")
            table.add_column("Description")
            for i, (id_, desc) in enumerate(choices, 1):
                marker = " ← default" if id_ == default else ""
                table.add_row(str(i), id_, desc + marker)
            self.console.print(table)

            while True:
                resp = Prompt.ask(f"[cyan]{message}[/cyan]", choices=[str(i) for i in range(1, len(choices)+1)], default=str(choices.index((default, '')) + 1) if default else "1")
                idx = int(resp) - 1
                if 0 <= idx < len(choices):
                    return choices[idx][0]
        else:
            print(f"\n{Colors.CYAN}{message}{Colors.RESET}")
            for i, (id_, desc) in enumerate(choices, 1):
                marker = f" {Colors.DIM}(default){Colors.RESET}" if id_ == default else ""
                print(f"  {i}. {Colors.BOLD}{id_}{Colors.RESET} - {desc}{marker}")
            while True:
                resp = input(f"\nChoice [1-{len(choices)}]: ").strip()
                if not resp and default:
                    return default
                try:
                    idx = int(resp) - 1
                    if 0 <= idx < len(choices):
                        return choices[idx][0]
                except ValueError:
                    pass
                print(f"Please enter 1-{len(choices)}")

    def select_multiple(self, message: str, choices: List[Tuple[str, str, bool]], default_selected: List[str] = None) -> List[str]:
        """Select multiple options. choices = [(id, description, recommended), ...]"""
        if default_selected is None:
            default_selected = []

        if self.use_rich:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Option", style="bold")
            table.add_column("Description")
            table.add_column("Rec.", style="green", width=4)
            for i, (id_, desc, rec) in enumerate(choices, 1):
                checked = "OK" if id_ in default_selected else " "
                rec_str = "*" if rec else ""
                table.add_row(str(i), f"[{checked}] {id_}", desc, rec_str)
            self.console.print(table)
            self.console.print("[dim]Enter numbers separated by commas (e.g., 1,3,5) or 'all'/'none'[/dim]")

            while True:
                resp = Prompt.ask("[cyan]Select options[/cyan]", default=','.join(str(choices.index(c)+1) for c in choices if c[0] in default_selected))
                if resp.lower() == 'all':
                    return [c[0] for c in choices]
                if resp.lower() == 'none':
                    return []
                try:
                    indices = [int(x.strip()) - 1 for x in resp.split(',')]
                    selected = [choices[i][0] for i in indices if 0 <= i < len(choices)]
                    return selected
                except ValueError:
                    self.console.print("[red]Invalid input. Use comma-separated numbers.[/red]")
        else:
            print(f"\n{Colors.CYAN}{message}{Colors.RESET}")
            for i, (id_, desc, rec) in enumerate(choices, 1):
                checked = f"{Colors.GREEN}[OK]{Colors.RESET}" if id_ in default_selected else f"{Colors.DIM}[ ]{Colors.RESET}"
                rec_str = f" {Colors.YELLOW}*{Colors.RESET}" if rec else ""
                print(f"  {i}. {checked} {Colors.BOLD}{id_}{Colors.RESET} - {desc}{rec_str}")
            print(f"\n{Colors.DIM}Enter numbers separated by commas (e.g., 1,3,5) or 'all'/'none'{Colors.RESET}")

            while True:
                resp = input(f"Selection: ").strip().lower()
                if resp == 'all':
                    return [c[0] for c in choices]
                if resp == 'none':
                    return []
                try:
                    indices = [int(x.strip()) - 1 for x in resp.split(',')]
                    selected = [choices[i][0] for i in indices if 0 <= i < len(choices)]
                    return selected
                except ValueError:
                    print(f"{Colors.RED}Invalid input. Use comma-separated numbers.{Colors.RESET}")

    def show_hardware_summary(self, hw, profile):
        """Display detected hardware and recommended profile."""
        self.print_header("HARDWARE DETECTED", "Review and confirm your system specifications")

        # Hardware table
        rows = [
            ["Operating System", f"{hw.os} {hw.os_version}"],
            ["Architecture", hw.arch],
            ["CPU", f"{hw.cpu.model} ({hw.cpu.cores}C / {hw.cpu.threads}T)"],
            ["RAM", f"{hw.ram_bytes / (1024**3):.1f} GB"],
        ]
        if hw.gpu:
            gpu = hw.gpu
            vram = f"{gpu.vram_bytes / (1024**3):.1f} GB VRAM" if gpu.vram_bytes > 0 else "Unified Memory"
            rows.append(["GPU", f"{gpu.vendor.upper()} {gpu.model} ({vram})"])
            if gpu.driver_version:
                rows.append(["GPU Driver", gpu.driver_version])
        else:
            rows.append(["GPU", "None detected"])
        if hw.platform_details.get("wsl"):
            rows.append(["Environment", "WSL2 (Linux on Windows)"])

        self.print_table("System Specifications", ["Component", "Details"], rows)

        # Profile recommendation
        self.print_header("RECOMMENDED PROFILE", f"Based on your hardware: {profile['name']} ({profile['tier']})")

        profile_rows = [
            ["Inference Stack", profile['recommended_stack']],
            ["Quantization", profile['quantization']],
            ["Context Window", f"{profile.get('context_window', 0):,} tokens"],
            ["GPU Memory Usage", f"{profile.get('gpu_memory_utilization', 0)*100:.0f}%"],
            ["CPU Offload (LMCache)", f"{profile.get('cpu_offload_gb', 0)} GB"],
        ]
        self.print_table("Profile Settings", ["Setting", "Value"], profile_rows)

        self.print_info(f"Notes: {profile['notes']}", "dim")
        self.print_info(f"Suggested models: {', '.join(profile['model_recommendations'])}", "dim")

        return self.confirm("Does this look correct?", default=True)

    def show_stack_options(self, profile, hw) -> Dict[str, bool]:
        """Present stack options with recommendations."""
        self.print_header("CHOOSE INFERENCE STACK", "Select the LLM serving stack to install. Only ONE can be active.")

        # Build choices based on hardware
        choices = []
        default_stack = profile['recommended_stack']

        # vLLM + LMCache
        if hw.gpu and hw.gpu.vendor in ('nvidia', 'amd') and hw.gpu.vram_bytes >= 4 * 1024**3:
            choices.append(("vllm_lmcache", "vLLM + LMCache (High-performance, GPU-accelerated)", default_stack == "vllm_lmcache"))
        elif hw.gpu and hw.gpu.vendor == 'apple':
            pass  # Not available on Apple Silicon
        else:
            choices.append(("vllm_lmcache", "vLLM + LMCache (Requires NVIDIA/AMD GPU with 4GB+ VRAM)", False))

        # Ollama
        if hw.gpu and hw.gpu.vendor == 'apple':
            choices.append(("ollama", "Ollama (Native Apple Silicon, excellent quantization)", default_stack == "ollama"))
        elif hw.os == 'Windows' and not hw.platform_details.get('wsl'):
            choices.append(("ollama", "Ollama (Native Windows, no WSL required)", default_stack == "ollama"))
        else:
            choices.append(("ollama", "Ollama (Cross-platform, easy model management)", default_stack == "ollama"))

        # llama.cpp
        choices.append(("llama_cpp", "llama.cpp (CPU/GPU via GGUF, most flexible, CPU-only friendly)", default_stack == "llama_cpp"))

        # CPU only option
        choices.append(("cpu_only", "Force CPU-only mode (llama.cpp with quantization)", False))

        stack_id = self.select_one("Choose inference stack:", choices, default_stack)

        # Return dict of all stacks with selected=True for chosen
        return {c[0]: (c[0] == stack_id) for c in choices}

    def show_additional_options(self, selected_stack: str, hw) -> Dict[str, bool]:
        """Present additional optional components."""
        self.print_header("ADDITIONAL COMPONENTS", "Optional components that enhance your installation")

        options = []
        defaults = []

        # CUDA Toolkit
        if selected_stack == "vllm_lmcache" and hw.gpu and hw.gpu.vendor == 'nvidia':
            options.append(("cuda_toolkit", "NVIDIA CUDA Toolkit (required for vLLM on NVIDIA)", True))
            defaults.append("cuda_toolkit")

        # ROCm
        if selected_stack == "vllm_lmcache" and hw.gpu and hw.gpu.vendor == 'amd':
            options.append(("rocm", "AMD ROCm (required for vLLM on AMD)", True))
            defaults.append("rocm")

        # Python venv
        if selected_stack in ("vllm_lmcache", "llama_cpp"):
            options.append(("python_venv", "Python Virtual Environment (isolated dependencies)", True))
            defaults.append("python_venv")

        # Models pre-download
        options.append(("models", "Pre-download models during install (saves time on first run)", False))

        # Auto-start service
        if hw.os == 'Linux' or hw.platform_details.get('wsl'):
            options.append(("systemd_service", "Systemd service for auto-start on boot", True))
            defaults.append("systemd_service")
        elif hw.os == 'Darwin':
            options.append(("launchd_service", "Launchd service for auto-start on login", True))
            defaults.append("launchd_service")
        elif hw.os == 'Windows' and selected_stack != "vllm_lmcache":
            options.append(("task_scheduler", "Windows Task Scheduler for auto-start", True))
            defaults.append("task_scheduler")

        if not options:
            self.print_info("No additional components recommended for this configuration.", "dim")
            return {}

        selected = self.select_multiple(
            "Select additional components to install:",
            [(o[0], o[1], o[2]) for o in options],
            defaults
        )

        return {o[0]: (o[0] in selected) for o in options}

    def show_model_selection(self, stack: str, profile, hw) -> Optional[str]:
        """Let user choose model."""
        self.print_header("MODEL SELECTION", f"Choose model for {stack}")

        models = profile['model_recommendations']
        choices = [(m, m, m == models[0]) for m in models]
        choices.append(("custom", "Enter custom HuggingFace model ID or Ollama name", False))

        selected = self.select_one("Select model:", choices, models[0])

        if selected == "custom":
            if self.use_rich:
                custom = Prompt.ask("[cyan]Enter model identifier[/cyan]")
            else:
                custom = input(f"{Colors.CYAN}Enter model identifier (HF ID or Ollama name): {Colors.RESET}").strip()
            return custom if custom else models[0]

        return selected

    def show_disk_space_warning(self, total_size_mb: int, available_mb: int):
        """Warn about disk space."""
        if total_size_mb > available_mb * 0.8:
            self.print_info(f"WARNING: Installation needs ~{total_size_mb} MB but only {available_mb} MB available", "warn")
            return self.confirm("Continue anyway?", default=False)
        return True

    def show_install_summary(self, selected: Dict[str, bool], model: str, hw, profile, install_dir) -> bool:
        """Show final summary and confirm installation."""
        self.print_header("INSTALLATION SUMMARY", "Review your choices before proceeding")

        # Selected components
        components = [k for k, v in selected.items() if v]
        if components:
            self.print_table("Components to Install", ["Component", "Status"],
                           [[c, "OK Selected" if selected[c] else "ERROR Skipped"] for c in self.options.keys() if c in selected],
                           ["bold", "green"])

        print(f"\n{Colors.BOLD if not self.use_rich else ''}Model:{Colors.RESET} {model}")
        print(f"{Colors.BOLD if not self.use_rich else ''}Install Directory:{Colors.RESET} {install_dir}")
        print(f"{Colors.BOLD if not self.use_rich else ''}API Endpoint:{Colors.RESET} http://localhost:{8000}/v1")

        # What will happen
        self.print_info("\nWhat will happen:", "info")
        steps = [
            "1. Create install directory and virtual environment",
            "2. Install selected components (downloads ~1-5 GB)",
            "3. Generate optimized configuration files",
            "4. Create launch scripts and system service (if selected)",
            "4. Generate client configs for cortex-agent, opencode, Continue.dev",
            "5. Optionally pre-download model (if selected)",
        ]
        for step in steps:
            print(f"  {step}")

        return self.confirm("\nProceed with installation?", default=True)

    def show_progress(self, message: str):
        """Show progress message."""
        if self.use_rich:
            self.console.print(f"[cyan]>> {message}[/cyan]")
        else:
            print(f"{Colors.CYAN}>> {message}{Colors.RESET}")

    def show_success(self, message: str):
        """Show success message."""
        if self.use_rich:
            self.console.print(f"[green]OK {message}[/green]")
        else:
            print(f"{Colors.GREEN}OK {message}{Colors.RESET}")

    def show_error(self, message: str):
        """Show error message."""
        if self.use_rich:
            self.console.print(f"[red]ERROR {message}[/red]")
        else:
            print(f"{Colors.RED}ERROR {message}{Colors.RESET}")

    def show_warning(self, message: str):
        """Show warning message."""
        if self.use_rich:
            self.console.print(f"[yellow]WARNING {message}[/yellow]")
        else:
            print(f"{Colors.YELLOW}WARNING {message}{Colors.RESET}")

    def prompt_model_download(self, model: str, stack: str) -> bool:
        """Ask if user wants to pre-download model."""
        size_estimate = "~16 GB (8B model)" if "8B" in model or "8b" in model else "~40 GB (70B model)" if "70B" in model or "70b" in model else "variable size"
        self.print_info(f"Model '{model}' will download on first use ({size_estimate})", "info")
        return self.confirm("Pre-download model now during installation?", default=False)

    def prompt_wsl_install(self) -> bool:
        """Ask about WSL2 installation on Windows."""
        self.print_header("WSL2 REQUIRED", "vLLM + LMCache requires Linux environment. On Windows, this means WSL2.")
        self.print_info("WSL2 (Windows Subsystem for Linux) allows running Linux binaries natively on Windows.", "info")
        self.print_info("The installer will:", "info")
        print("  1. Enable WSL2 feature (requires reboot)")
        print("  2. Install Ubuntu 24.04 distribution")
        print("  3. Configure GPU passthrough for your NVIDIA GPU")
        print("  4. Install vLLM + LMCache inside Ubuntu")
        self.print_info("Your Windows files will be accessible at /mnt/c/ inside WSL2", "dim")
        return self.confirm("\nInstall WSL2 now? (Requires admin rights and reboot)", default=True)

    def show_post_install(self, install_dir, model, stack, port, client_configs):
        """Show post-installation instructions."""
        self.print_header("INSTALLATION COMPLETE", "Your local LLM stack is ready!")

        print(f"\n{Colors.BOLD}Install Directory:{Colors.RESET} {install_dir}")
        print(f"{Colors.BOLD}Model:{Colors.RESET} {model}")
        print(f"{Colors.BOLD}Stack:{Colors.RESET} {stack}")
        print(f"{Colors.BOLD}API Endpoint:{Colors.RESET} http://localhost:{port}/v1")

        self.print_header("CLIENT CONFIGURATIONS", "Copy these to your AI coding agents:")

        for name, path in client_configs.items():
            print(f"\n  {Colors.BOLD}{name}:{Colors.RESET} {path}")

        self.print_header("NEXT STEPS")

        if stack == "vllm_lmcache":
            print("  1. Install systemd service (run once with sudo):")
            print(f"     sudo cp {install_dir}/service/llm-stack.service /etc/systemd/system/")
            print("     sudo systemctl daemon-reload && sudo systemctl enable llm-stack && sudo systemctl start llm-stack")
            print("  2. Or run manually:")
            print(f"     {install_dir}/start.sh")
        elif stack == "ollama":
            print("  1. Start Ollama service:")
            print("     ollama serve")
            print("  2. Pull model (if not pre-downloaded):")
            print(f"     ollama pull {model}")
        else:
            print("  1. Run manually:")
            print(f"     {install_dir}/start.sh")

        print(f"\n  3. Test the API:")
        print(f"     curl http://localhost:{port}/v1/models")

        print(f"\n  4. Configure your agents (see client-configs/ directory)")

    def check_prerequisites(self, hw, selected: Dict[str, bool]) -> List[str]:
        """Check and return list of missing prerequisites."""
        missing = []

        if selected.get("vllm"):
            if hw.gpu and hw.gpu.vendor == 'nvidia':
                if not hw.gpu.driver_version:
                    missing.append("NVIDIA GPU driver (install from nvidia.com)")
            if hw.os == 'Windows' and not hw.platform_details.get('wsl'):
                missing.append("WSL2 (Windows Subsystem for Linux)")

        if selected.get("ollama") and hw.os == 'Darwin':
            # Check Homebrew
            import shutil
            if not shutil.which('brew'):
                missing.append("Homebrew (install from brew.sh)")

        if selected.get("python_venv"):
            if sys.version_info < (3, 10):
                missing.append("Python 3.10+ (current: {}.{})".format(sys.version_info.major, sys.version_info.minor))

        return missing