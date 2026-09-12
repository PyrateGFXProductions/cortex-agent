# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Hardware-aware automatic configuration for local LLM stacks
- Smart installer with interactive UI and hardware detection
- WSL2 + vLLM + LMCache setup for Windows
- File staleness detection via `os.stat(mtime, size)`
- Opencode patch (private) with all 5 efficiency patterns

### Changed
- Renamed package from `neuralcode` to `cortex_agent`
- Updated description to "Reference implementation of context-window efficiency patterns"
- Moved AVB attribution to Credits section
- Replaced Patreon with Ko-Fi support link

### Fixed
- pyproject.toml metadata (author, classifiers, URLs, keywords)
- Added LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT

## [0.2.0] - 2024-01-15

### Added
- MCP server (`cortex_agent/mcp_server.py`) exposing tools via Model Context Protocol
- Distribution files: `install.sh`, `install.ps1`
- AGENTS.md for AI harness auto-discovery

### Performance
- `context.py`: Replaced per-turn MD5 hashing with `os.stat()` (mtime, size)
- `context.py`: Cached git branch for process lifetime
- `history.py`: `locked()` result cached by message list length (O(1))
- `history.py`: `sweep()` registered via `atexit` for crash cleanup
- `session.py`: `all_sessions()` stops at first user message
- `tools.py`: `str_replace` uses `find()`-based single-pass validation

### Removed
- Dead code: `neuralcode/intelligence/pressure_response.py`
- `GLOBAL_DISTRIBUTION_GUIDE.md`
- Duplicate package entry in `uv.lock`

## [0.1.0] - 2023-XX-XX

### Added
- Initial fork from [avbiswas/neural-code](https://github.com/avbiswas/neural-code)
- Core agent loop with tool execution
- Subagent system for isolated exploration
- Context compaction (85% → 35%)
- Three-tier tool output degradation (cap/strip/drop)
- Late injection for prompt cache preservation
- File staleness detection
- Skills system
- Session persistence (JSONL)
- Sandbox (seatbelt/bubblewrap)
- Permissions system
- UI with Rich + prompt_toolkit