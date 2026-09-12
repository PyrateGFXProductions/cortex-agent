# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | ✅ Yes             |
| < 0.2   | ❌ No              |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities via public GitHub issues.**

Instead, report them privately via:

**Email:** pyrategfxproductions@gmail.com  
**Subject:** `[SECURITY] cortex-agent - <brief description>`

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive acknowledgment within 48 hours. We aim to provide a fix timeline within 7 days.

## Scope

This policy covers:
- The `cortex-agent` Python package
- The smart installer (`smart_installer/`)
- The WSL2 setup script
- MCP server (`cortex_agent/mcp_server.py`)

Out of scope:
- Third-party dependencies (report to their maintainers)
- User configuration files (`~/.agents/env`)
- Local LLM stacks installed via smart installer (vLLM, Ollama, llama.cpp)

## Security Considerations

### Sandboxing
- macOS: Seatbelt profile restricts filesystem/network
- Linux: bubblewrap restricts filesystem/network
- Windows: No kernel sandbox (graceful fallback)

### Permissions
- Bash commands: allow/deny/ask rules
- File writes outside project: prompt required
- MCP server: no API key required, local tools only

### API Keys
- Stored in `~/.agents/env` (user-controlled, not committed)
- Never logged or transmitted except to configured provider

### Local LLM Stack (Smart Installer)
- Runs locally, no external API calls for inference
- Model downloads from Hugging Face (HTTPS, verified)
- LMCache offloads to local CPU RAM/disk only

## Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Acknowledgment + triage
3. **Day 3-7**: Fix developed + tested
4. **Day 7-14**: Patch released + advisory published
5. **Day 14+**: Public disclosure (if not already)

We credit reporters in advisories unless anonymity is requested.