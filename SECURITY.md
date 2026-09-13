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
- The smart installer patcher (`smart_installer/`)
- MCP server (`cortex_agent/mcp_server.py`)

Out of scope:
- Third-party dependencies (report to their maintainers)
- User configuration files (`~/.agents/env`)
- The code of external clients that `smart_installer/` patches (each repo's own policy applies)

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

### Smart Installer (`smart_installer/`)
- Probes and patches **source code only**; it never downloads or installs binaries
- Requires a git checkout before editing (unless `--force`); edits are backed up
- `--dry-run` shows exact diffs and writes nothing

## Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Acknowledgment + triage
3. **Day 3-7**: Fix developed + tested
4. **Day 7-14**: Patch released + advisory published
5. **Day 14+**: Public disclosure (if not already)

We credit reporters in advisories unless anonymity is requested.