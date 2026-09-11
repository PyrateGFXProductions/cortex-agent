#!/usr/bin/env python3
"""
Cross-platform hardware detection for smart installer.
Detects GPU (vendor, model, VRAM), CPU, RAM, OS.
"""

import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class GPUInfo:
    vendor: str  # "nvidia", "amd", "intel", "apple", "unknown"
    model: str
    vram_bytes: int  # 0 if unknown or unified memory
    unified_memory: bool
    driver_version: str = ""
    compute_capability: str = ""


@dataclass
class CPUInfo:
    model: str
    cores: int
    threads: int
    architecture: str


@dataclass
class HardwareInfo:
    os: str
    os_version: str
    arch: str
    cpu: CPUInfo
    ram_bytes: int
    gpu: Optional[GPUInfo]
    platform_details: Dict[str, Any]


def run_cmd(cmd: list, timeout: int = 10) -> tuple[str, str, int]:
    """Run command, return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as e:
        return "", str(e), 1


def get_system_ram() -> int:
    """Get total system RAM in bytes."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb * 1024
        except Exception:
            pass
    elif system == "Darwin":
        out, _, code = run_cmd(["sysctl", "-n", "hw.memsize"])
        if code == 0:
            return int(out)
    elif system == "Windows":
        out, _, code = run_cmd(["wmic", "ComputerSystem", "get", "TotalPhysicalMemory", "/value"])
        if code == 0:
            for line in out.splitlines():
                if "=" in line:
                    return int(line.split("=")[1].strip())
    return 0


def get_cpu_info() -> CPUInfo:
    """Get CPU information."""
    system = platform.system()
    model = platform.processor() or platform.machine()
    cores = os.cpu_count() or 1
    threads = cores
    arch = platform.machine()

    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name") and not model:
                        model = line.split(":", 1)[1].strip()
                    elif line.startswith("cpu cores"):
                        cores = int(line.split(":")[1].strip())
                    elif line.startswith("siblings"):
                        threads = int(line.split(":")[1].strip())
        except Exception:
            pass
    elif system == "Darwin":
        out, _, code = run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
        if code == 0:
            model = out
        out, _, code = run_cmd(["sysctl", "-n", "hw.physicalcpu"])
        if code == 0:
            cores = int(out)
        out, _, code = run_cmd(["sysctl", "-n", "hw.logicalcpu"])
        if code == 0:
            threads = int(out)
    elif system == "Windows":
        out, _, code = run_cmd(["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors", "/format:csv"])
        if code == 0:
            lines = out.strip().splitlines()
            if len(lines) > 1:
                parts = lines[1].split(",")
                if len(parts) >= 4:
                    model = parts[1].strip()
                    cores = int(parts[2].strip())
                    threads = int(parts[3].strip())

    return CPUInfo(model=model, cores=cores, threads=threads, architecture=arch)


def detect_nvidia_gpu() -> Optional[GPUInfo]:
    """Detect NVIDIA GPU via nvidia-smi."""
    out, _, code = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader,nounits"])
    if code != 0 or not out:
        return None

    lines = out.strip().splitlines()
    if not lines:
        return None

    # Use first GPU
    parts = [p.strip() for p in lines[0].split(",")]
    if len(parts) >= 3:
        model = parts[0]
        vram_mb = int(parts[1]) if parts[1].isdigit() else 0
        driver = parts[2] if len(parts) > 2 else ""
        compute_cap = parts[3] if len(parts) > 3 else ""

        return GPUInfo(
            vendor="nvidia",
            model=model,
            vram_bytes=vram_mb * 1024 * 1024,
            unified_memory=False,
            driver_version=driver,
            compute_capability=compute_cap
        )
    return None


def detect_amd_gpu_linux() -> Optional[GPUInfo]:
    """Detect AMD GPU on Linux via rocm-smi or lspci."""
    # Try rocm-smi first
    out, _, code = run_cmd(["rocm-smi", "--showproductname", "--showvramtotal", "--json"])
    if code == 0 and out:
        try:
            data = json.loads(out)
            # Parse rocm-smi JSON output
            for gpu_id, info in data.items():
                if isinstance(info, dict):
                    model = info.get("Card series", info.get("Product Name", "AMD GPU"))
                    vram_str = info.get("VRAM Total", "0")
                    vram_mb = int(re.sub(r"[^\d]", "", vram_str)) if vram_str else 0
                    return GPUInfo(
                        vendor="amd",
                        model=model,
                        vram_bytes=vram_mb * 1024 * 1024 if vram_mb else 0,
                        unified_memory=False
                    )
        except Exception:
            pass

    # Fallback to lspci
    out, _, code = run_cmd(["lspci", "-nn"])
    if code == 0:
        for line in out.splitlines():
            if re.search(r"(VGA|3D|Display).*AMD|ATI", line, re.IGNORECASE):
                return GPUInfo(
                    vendor="amd",
                    model=line.strip(),
                    vram_bytes=0,
                    unified_memory=False
                )
    return None


def detect_intel_gpu_linux() -> Optional[GPUInfo]:
    """Detect Intel GPU on Linux via lspci."""
    out, _, code = run_cmd(["lspci", "-nn"])
    if code == 0:
        for line in out.splitlines():
            if re.search(r"(VGA|3D|Display).*Intel", line, re.IGNORECASE):
                return GPUInfo(
                    vendor="intel",
                    model=line.strip(),
                    vram_bytes=0,
                    unified_memory=False
                )
    return None


def detect_gpu_linux() -> Optional[GPUInfo]:
    """Detect GPU on Linux."""
    # Try NVIDIA first
    gpu = detect_nvidia_gpu()
    if gpu:
        return gpu

    # Try AMD
    gpu = detect_amd_gpu_linux()
    if gpu:
        return gpu

    # Try Intel
    gpu = detect_intel_gpu_linux()
    if gpu:
        return gpu

    return None


def detect_gpu_windows() -> Optional[GPUInfo]:
    """Detect GPU on Windows."""
    # Try NVIDIA first
    gpu = detect_nvidia_gpu()
    if gpu:
        return gpu

    # Try WMI for any GPU
    out, _, code = run_cmd(["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM,DriverVersion", "/format:csv"])
    if code == 0:
        lines = out.strip().splitlines()
        for line in lines[1:]:  # Skip header
            parts = line.split(",")
            if len(parts) >= 4:
                name = parts[1].strip()
                vram_str = parts[2].strip()
                driver = parts[3].strip()
                if name and vram_str.isdigit():
                    vram = int(vram_str)
                    vendor = "unknown"
                    name_lower = name.lower()
                    if "nvidia" in name_lower or "geforce" in name_lower or "quadro" in name_lower or "rtx" in name_lower:
                        vendor = "nvidia"
                    elif "amd" in name_lower or "radeon" in name_lower:
                        vendor = "amd"
                    elif "intel" in name_lower or "iris" in name_lower or "arc" in name_lower:
                        vendor = "intel"
                    return GPUInfo(
                        vendor=vendor,
                        model=name,
                        vram_bytes=vram,
                        unified_memory=False,
                        driver_version=driver
                    )
    return None


def detect_gpu_macos() -> Optional[GPUInfo]:
    """Detect GPU on macOS (Apple Silicon)."""
    out, _, code = run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
    if code == 0:
        cpu = out.lower()
        if "apple" in cpu:
            chip = "Apple Silicon"
            if "m1" in cpu:
                chip = "Apple M1"
            elif "m2" in cpu:
                chip = "Apple M2"
            elif "m3" in cpu:
                chip = "Apple M3"
            elif "m4" in cpu:
                chip = "Apple M4"

            if "ultra" in cpu:
                chip += " Ultra"
            elif "max" in cpu:
                chip += " Max"
            elif "pro" in cpu:
                chip += " Pro"

            return GPUInfo(
                vendor="apple",
                model=chip,
                vram_bytes=0,  # Unified memory
                unified_memory=True
            )

    # Intel Mac - try system_profiler
    out, _, code = run_cmd(["system_profiler", "SPDisplaysDataType"])
    if code == 0:
        # Parse for discrete GPU
        for line in out.splitlines():
            if "Chipset Model" in line and "Intel" not in line:
                model = line.split(":")[1].strip()
                vendor = "amd" if "AMD" in model or "Radeon" in model else "unknown"
                return GPUInfo(
                    vendor=vendor,
                    model=model,
                    vram_bytes=0,
                    unified_memory=False
                )
    return None


def detect_gpu() -> Optional[GPUInfo]:
    """Detect GPU based on platform."""
    system = platform.system()
    if system == "Linux":
        return detect_gpu_linux()
    elif system == "Windows":
        return detect_gpu_windows()
    elif system == "Darwin":
        return detect_gpu_macos()
    return None


def get_os_version() -> str:
    """Get OS version string."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return f"Linux {platform.release()}"
    elif system == "Darwin":
        out, _, code = run_cmd(["sw_vers", "-productVersion"])
        if code == 0:
            return f"macOS {out}"
        return f"macOS {platform.mac_ver()[0]}"
    elif system == "Windows":
        return f"Windows {platform.version()}"
    return system


def detect_hardware() -> HardwareInfo:
    """Main detection function."""
    gpu = detect_gpu()
    cpu = get_cpu_info()
    ram = get_system_ram()

    # Platform-specific details
    platform_details = {}
    if platform.system() == "Linux":
        platform_details["wsl"] = "microsoft" in platform.uname().release.lower()
    elif platform.system() == "Windows":
        platform_details["wsl_available"] = check_wsl_available()

    return HardwareInfo(
        os=platform.system(),
        os_version=get_os_version(),
        arch=platform.machine(),
        cpu=cpu,
        ram_bytes=ram,
        gpu=gpu,
        platform_details=platform_details
    )


def check_wsl_available() -> bool:
    """Check if WSL2 is available on Windows."""
    out, _, code = run_cmd(["wsl", "--list", "--verbose"])
    return code == 0 and "Ubuntu" in out


def get_hardware_profile(hw: HardwareInfo) -> Dict[str, Any]:
    """Determine hardware profile and recommended settings."""
    ram_gb = hw.ram_bytes / (1024**3)
    gpu = hw.gpu

    profile = {
        "name": "cpu_only",
        "tier": "cpu_only",
        "recommended_stack": "llama.cpp",
        "quantization": "Q4_K_M",
        "context_window": 8192,
        "gpu_memory_utilization": 0.0,
        "cpu_offload_gb": 0,
        "model_recommendations": [
            "microsoft/Phi-3.5-mini-instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "google/gemma-2-2b-it"
        ],
        "notes": "No GPU detected. Using CPU-only inference with llama.cpp."
    }

    if gpu:
        if gpu.vendor == "apple" or gpu.unified_memory:
            # Apple Silicon unified memory
            if ram_gb >= 96:
                profile.update({
                    "name": "apple_silicon_high",
                    "tier": "high_end",
                    "recommended_stack": "ollama",
                    "quantization": "Q4_K_M",
                    "context_window": 65536,
                    "cpu_offload_gb": int(ram_gb * 0.5),
                    "model_recommendations": [
                        "llama3.1:70b",
                        "qwen2.5:32b",
                        "deepseek-r1:32b"
                    ],
                    "notes": "Apple Silicon with high unified memory. Use Ollama with large models."
                })
            elif ram_gb >= 64:
                profile.update({
                    "name": "apple_silicon_mid",
                    "tier": "mid_range",
                    "recommended_stack": "ollama",
                    "quantization": "Q4_K_M",
                    "context_window": 32768,
                    "cpu_offload_gb": int(ram_gb * 0.5),
                    "model_recommendations": [
                        "llama3.1:8b",
                        "qwen2.5:14b",
                        "codellama:13b"
                    ],
                    "notes": "Apple Silicon with good unified memory. Ollama recommended."
                })
            elif ram_gb >= 32:
                profile.update({
                    "name": "apple_silicon_entry",
                    "tier": "low_end",
                    "recommended_stack": "ollama",
                    "quantization": "Q4_K_M",
                    "context_window": 16384,
                    "cpu_offload_gb": int(ram_gb * 0.4),
                    "model_recommendations": [
                        "llama3.1:8b",
                        "phi3.5:3.8b",
                        "qwen2.5:7b"
                    ],
                    "notes": "Apple Silicon with limited unified memory. Use smaller quantized models."
                })
            else:
                profile.update({
                    "name": "apple_silicon_minimal",
                    "tier": "cpu_only",
                    "recommended_stack": "ollama",
                    "quantization": "Q4_K_M",
                    "context_window": 8192,
                    "cpu_offload_gb": int(ram_gb * 0.3),
                    "model_recommendations": [
                        "phi3.5:3.8b",
                        "gemma2:2b",
                        "qwen2.5:3b"
                    ],
                    "notes": "Low unified memory. Use very small models only."
                })

        elif gpu.vram_bytes > 0:
            # Discrete GPU with known VRAM
            vram_gb = gpu.vram_bytes / (1024**3)

            if vram_gb >= 24:
                profile.update({
                    "name": "high_end",
                    "tier": "high_end",
                    "recommended_stack": "vllm_lmcache",
                    "quantization": "FP16",
                    "context_window": 131072,
                    "gpu_memory_utilization": 0.9,
                    "cpu_offload_gb": min(int(ram_gb * 0.5), 64),
                    "model_recommendations": [
                        "meta-llama/Llama-3.1-70B-Instruct",
                        "Qwen/Qwen2.5-72B-Instruct",
                        "mistralai/Mixtral-8x22B-Instruct"
                    ],
                    "notes": f"High-end {gpu.vendor.upper()} GPU ({vram_gb:.0f}GB VRAM). vLLM + LMCache for maximum performance."
                })
            elif vram_gb >= 16:
                profile.update({
                    "name": "high_end",
                    "tier": "high_end",
                    "recommended_stack": "vllm_lmcache",
                    "quantization": "FP16",
                    "context_window": 65536,
                    "gpu_memory_utilization": 0.85,
                    "cpu_offload_gb": min(int(ram_gb * 0.5), 48),
                    "model_recommendations": [
                        "meta-llama/Llama-3.1-70B-Instruct",
                        "Qwen/Qwen2.5-32B-Instruct",
                        "codellama/CodeLlama-34b-Instruct-hf"
                    ],
                    "notes": f"High-end {gpu.vendor.upper()} GPU ({vram_gb:.0f}GB VRAM). vLLM + LMCache recommended."
                })
            elif vram_gb >= 12:
                profile.update({
                    "name": "mid_range",
                    "tier": "mid_range",
                    "recommended_stack": "vllm_lmcache",
                    "quantization": "FP16",
                    "context_window": 32768,
                    "gpu_memory_utilization": 0.85,
                    "cpu_offload_gb": min(int(ram_gb * 0.5), 32),
                    "model_recommendations": [
                        "meta-llama/Llama-3.1-8B-Instruct",
                        "Qwen/Qwen2.5-14B-Instruct",
                        "codellama/CodeLlama-13b-Instruct-hf"
                    ],
                    "notes": f"Mid-range {gpu.vendor.upper()} GPU ({vram_gb:.0f}GB VRAM). vLLM + LMCache with CPU offload."
                })
            elif vram_gb >= 8:
                profile.update({
                    "name": "mid_range",
                    "tier": "mid_range",
                    "recommended_stack": "vllm_lmcache",
                    "quantization": "8bit",
                    "context_window": 32768,
                    "gpu_memory_utilization": 0.8,
                    "cpu_offload_gb": min(int(ram_gb * 0.4), 24),
                    "model_recommendations": [
                        "meta-llama/Llama-3.1-8B-Instruct",
                        "Qwen/Qwen2.5-7B-Instruct",
                        "microsoft/Phi-3.5-mini-instruct"
                    ],
                    "notes": f"Entry {gpu.vendor.upper()} GPU ({vram_gb:.0f}GB VRAM). 8-bit quantization recommended."
                })
            elif vram_gb >= 4:
                profile.update({
                    "name": "low_end",
                    "tier": "low_end",
                    "recommended_stack": "vllm_lmcache",
                    "quantization": "4bit",
                    "context_window": 16384,
                    "gpu_memory_utilization": 0.75,
                    "cpu_offload_gb": min(int(ram_gb * 0.3), 16),
                    "model_recommendations": [
                        "microsoft/Phi-3.5-mini-instruct",
                        "Qwen/Qwen2.5-3B-Instruct",
                        "google/gemma-2-2b-it"
                    ],
                    "notes": f"Low VRAM {gpu.vendor.upper()} GPU ({vram_gb:.0f}GB). 4-bit quantization required."
                })

    return profile


def main():
    """Main entry point for hardware detection."""
    import argparse
    parser = argparse.ArgumentParser(description="Detect hardware for LLM inference stack")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--profile", action="store_true", help="Include recommended profile")
    args = parser.parse_args()

    hw = detect_hardware()
    result = {"hardware": asdict(hw)}

    if args.profile:
        result["profile"] = get_hardware_profile(hw)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        hw_dict = asdict(hw)
        print(f"OS: {hw_dict['os']} {hw_dict['os_version']}")
        print(f"Arch: {hw_dict['arch']}")
        print(f"CPU: {hw_dict['cpu']['model']} ({hw_dict['cpu']['cores']}C/{hw_dict['cpu']['threads']}T)")
        print(f"RAM: {hw_dict['ram_bytes'] / (1024**3):.1f} GB")

        if hw_dict['gpu']:
            gpu = hw_dict['gpu']
            vram_str = f"{gpu['vram_bytes'] / (1024**3):.1f} GB VRAM" if gpu['vram_bytes'] > 0 else "Unified Memory"
            print(f"GPU: {gpu['vendor'].upper()} {gpu['model']} ({vram_str})")
        else:
            print("GPU: None detected")

        if args.profile:
            prof = result["profile"]
            print(f"\nRecommended Profile: {prof['name']} ({prof['tier']})")
            print(f"Stack: {prof['recommended_stack']}")
            print(f"Quantization: {prof['quantization']}")
            print(f"Context Window: {prof['context_window']:,}")
            print(f"GPU Memory Utilization: {prof['gpu_memory_utilization']*100:.0f}%")
            print(f"CPU Offload: {prof['cpu_offload_gb']} GB")
            print(f"Notes: {prof['notes']}")
            print(f"Suggested Models: {', '.join(prof['model_recommendations'])}")


if __name__ == "__main__":
    main()