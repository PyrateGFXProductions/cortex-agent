#!/usr/bin/env bash
# install.sh — set up cortex-agent on macOS or Linux
set -euo pipefail

AGENTS_DIR="$HOME/.agents"
ENV_FILE="$AGENTS_DIR/env"

echo "==> cortex-agent installer"

# 1. Ensure uv is available
if ! command -v uv &>/dev/null; then
  echo "==> Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

# 2. Install the package + MCP adapter as a uv tool
echo "==> Installing cortex-agent..."
uv tool install ".[mcp]" --force

# 3. Create ~/.agents/env if it doesn't exist
mkdir -p "$AGENTS_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
# cortex-agent configuration
# OpenRouter (recommended): https://openrouter.ai/keys
BASE_URL=https://openrouter.ai/api/v1
# API_KEY=  (run `cortex-agent` - the setup wizard will ask, or paste your key here)

# Optional — defaults shown
# MODEL=deepseek/deepseek-v4-flash
# CONTEXT_WINDOW=128000
EOF
  echo "==> Created $ENV_FILE — edit it to add your API key"
else
  echo "==> $ENV_FILE already exists, skipping"
fi

echo ""
echo "Done. Run 'cortex-agent' from any project directory."
echo ""
echo "To use with Claude Desktop / Cursor / Windsurf, add to your MCP config:"
echo ""
cat <<'EOF'
{
  "mcpServers": {
    "cortex-agent": {
      "command": "cortex-agent-mcp"
    }
  }
}
EOF
echo ""
echo "Config file locations:"
echo "  Claude Desktop:  ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "  Cursor:          ~/.cursor/mcp.json"
echo "  Windsurf:        ~/.codeium/windsurf/mcp_settings.json"
