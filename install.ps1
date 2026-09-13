# install.ps1 — set up cortex-agent on Windows
# Run from the repo root: .\install.ps1
$ErrorActionPreference = "Stop"

$AgentsDir = Join-Path $env:USERPROFILE ".agents"
$EnvFile   = Join-Path $AgentsDir "env"

Write-Host "==> cortex-agent installer" -ForegroundColor Cyan

# 1. Ensure uv is available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing uv..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    # Reload PATH so uv is visible in this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" + $env:PATH
}

# 2. Install the package + MCP adapter as a uv tool
Write-Host "==> Installing cortex-agent..." -ForegroundColor Yellow
uv tool install ".[mcp]" --force

# 3. Create ~/.agents/env if it doesn't exist
if (-not (Test-Path $AgentsDir)) { New-Item -ItemType Directory -Path $AgentsDir | Out-Null }

if (-not (Test-Path $EnvFile)) {
    @"
# cortex-agent configuration
# OpenRouter (recommended): https://openrouter.ai/keys
BASE_URL=https://openrouter.ai/api/v1
# API_KEY=  (run `cortex-agent` - the setup wizard will ask, or paste your key here)

# Optional — defaults shown
# MODEL=deepseek/deepseek-v4-flash
# CONTEXT_WINDOW=128000
"@ | Set-Content -Path $EnvFile -Encoding UTF8
    Write-Host "==> Created $EnvFile — edit it to add your API key" -ForegroundColor Green
} else {
    Write-Host "==> $EnvFile already exists, skipping" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done. Run 'cortex-agent' from any project directory." -ForegroundColor Green
Write-Host ""
Write-Host "To use with Claude Desktop / Cursor / Windsurf, add to your MCP config:" -ForegroundColor Cyan
Write-Host ""
Write-Host @'
{
  "mcpServers": {
    "cortex-agent": {
      "command": "cortex-agent-mcp"
    }
  }
}
'@ -ForegroundColor White
Write-Host ""
Write-Host "Config file locations:"
Write-Host "  Claude Desktop:  %APPDATA%\Claude\claude_desktop_config.json"
Write-Host "  Cursor:          %USERPROFILE%\.cursor\mcp.json"
Write-Host "  Windsurf:        %USERPROFILE%\.codeium\windsurf\mcp_settings.json"
