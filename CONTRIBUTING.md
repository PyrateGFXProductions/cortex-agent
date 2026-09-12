# Contributing to cortex-agent

Thank you for your interest in contributing! This document outlines the process for contributing to cortex-agent.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before opening an issue, please:
1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - OS, Python version, hardware (GPU/CPU/RAM)
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs (with sensitive data redacted)

### Suggesting Features

Feature requests are welcome! Please:
1. Check existing issues/discussions first
2. Use the feature request template
3. Explain the use case and expected behavior
4. Consider implementation complexity

### Pull Requests

1. **Fork** the repository
2. **Create a branch** from `main`: `git checkout -b feature/your-feature-name`
3. **Make changes** following the code style
4. **Run tests**: `pytest` (when available)
5. **Run linting**: `ruff check . && black --check .`
6. **Commit** with clear messages
7. **Push** and open a PR against `main`

## Development Setup

```bash
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
uv sync --dev
uv run pytest  # when tests are added
uv run ruff check .
uv run black --check .
```

## Code Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff (with strict rules)
- **Type checking**: MyPy (strict mode)
- **Commits**: Conventional Commits format

## Testing

Run the test suite:
```bash
uv run pytest -v
```

## Documentation

- Update relevant `.md` files for any user-facing changes
- Docstrings follow Google style
- Update `CHANGELOG.md` for notable changes

## Release Process

Maintainers handle releases:
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Tag release: `git tag vX.Y.Z`
4. GitHub Actions builds and publishes

## Questions?

Open a discussion or reach out via [GitHub Issues](https://github.com/PyrateGFXProductions/cortex-agent/issues).