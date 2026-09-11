<#
.SYNOPSIS
    Smart LLM Inference Stack Installer - PowerShell wrapper for Windows
.DESCRIPTION
    Detects hardware and installs optimal local LLM stack with LMCache.
    Supports vLLM+LMCache (WSL2), Ollama (native), llama.cpp (fallback).
.NOTES
    Run from PowerShell. For vLLM on Windows, requires WSL2.
#>

param(
    [string]$Model,
    [int]$Port = 8000,
    [string]$Quantization,
    [switch]$CpuOnly,
    [switch]$DryRun,
    [switch]$ForceWsl
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path $ScriptDir "smart_installer\smart_install.py"

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "Python not found. Install Python 3.10+ from https://python.org"
    exit 1
}

# Build arguments
$args = @()
if ($Model) { $args += "--model", $Model }
if ($Port) { $args += "--port", $Port }
if ($Quantization) { $args += "--quantization", $Quantization }
if ($CpuOnly) { $args += "--cpu-only" }
if ($DryRun) { $args += "--dry-run" }
if ($ForceWsl) { $args += "--force-wsl" }

# Run
Write-Host "Starting Smart Installer..." -ForegroundColor Cyan
& $python.Source $PythonScript @args
exit $LASTEXITCODE