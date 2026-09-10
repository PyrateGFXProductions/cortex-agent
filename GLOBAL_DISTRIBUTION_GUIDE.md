# Global Distribution Strategy for Cortex-Agent Intelligence Modules

## Overview

This guide explains how to distribute the intelligence enhancements (tool optimizer, budget forecaster, pressure response, etc.) **globally** so that every user who has cortex-agent installed automatically benefits from them.

We use **three-tier distribution**:
1. **Core Distribution** (via PyPI/package manager)
2. **Configuration Distribution** (via ~/.agents/config)
3. **Plugin Distribution** (via ~/.agents/plugins)

---

## Architecture Diagram

```
User Installation
     ↓
[pip install neuralcode]
     ↓
System packages:
  ├─ neuralcode (core agent)
  └─ Intelligence modules (new)
       ├─ tool_optimizer.py
       ├─ budget_forecaster.py
       ├─ pressure_response.py
       └─ teaching_mode.py
     ↓
User Config (~/.agents/)
     ├─ env (credentials)
     ├─ config.yaml (global settings)
     ├─ skills/ (custom skills)
     ├─ plugins/ (experimental)
     └─ cache/ (tool call history)
     ↓
Runtime:
  neuralcode --mode=intelligent (loads all modules)
  neuralcode --mode=minimal (original behavior)
  neuralcode --teach (show optimization decisions)
```

---

## Step 1: Package the Intelligence Modules in PyPI

### Current Structure → Target Structure

```
neuralcode/
├── agent.py (UPDATED: loads intelligence)
├── config.py (UPDATED: adds mode/feature flags)
├── tools.py
├── ui.py
├── commands.py
├── history.py
│
└── intelligence/ (NEW DIRECTORY)
    ├── __init__.py
    ├── base.py (Abstract base for all modules)
    ├── tool_optimizer.py
    ├── budget_forecaster.py
    ├── pressure_response.py
    ├── smart_tools.py
    ├── teaching_mode.py
    └── registry.py (Module loader)
```

### Update `pyproject.toml` for Distribution

```toml
[project]
name = "neuralcode"
version = "0.2.0"
description = "A minimal coding agent with intelligent optimizations"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "openai>=3.5.0",
    "prompt-toolkit>=3.0.53",
    "pyyaml>=6.0.3",
    "rich>=15.0.0",
]

# OPTIONAL: AI enhancement features
[project.optional-dependencies]
intelligence = [
    # These are bundled now, so no extra deps
]

[project.scripts]
neuralcode = "neuralcode.agent:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.urls]
Repository = "https://github.com/PyrateGFXProductions/cortex-agent"
Changelog = "https://github.com/PyrateGFXProductions/cortex-agent/releases"

[tool.hatch.version]
path = "neuralcode/__version__.py"
```

---

## Step 2: Create Intelligence Module Base & Registry

### `neuralcode/intelligence/base.py`

```python
"""Abstract base for all intelligence modules."""

from abc import ABC, abstractmethod
from enum import Enum


class ModulePhase(Enum):
    """When a module runs in the agent lifecycle."""
    PRE_LLM = "before_llm_call"
    POST_LLM = "after_llm_response"
    TOOL_INTERCEPT = "intercept_tool_call"
    POST_TOOL = "after_tool_execution"
    CONTEXT_CHECK = "check_context_pressure"


class IntelligenceModule(ABC):
    """All intelligence modules inherit from this."""
    
    name: str
    description: str
    enabled_by_default: bool = True
    phase: ModulePhase = ModulePhase.PRE_LLM
    
    def __init__(self, config=None, ui=None):
        self.config = config or {}
        self.ui = ui
        self.logger = None
    
    @abstractmethod
    def can_run(self) -> bool:
        """Return False if preconditions not met (e.g., insufficient context)."""
        pass
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """Run this module. Returns modified state or recommendation."""
        pass
    
    def log(self, level, message):
        """Log to teaching mode if enabled."""
        if self.logger:
            getattr(self.logger, level)(message)
    
    def __repr__(self):
        return f"{self.name} ({'enabled' if self.enabled_by_default else 'disabled'})"
```

### `neuralcode/intelligence/registry.py`

```python
"""Module registry: load, enable/disable, and orchestrate intelligence modules."""

import importlib
import logging
from pathlib import Path
from typing import List, Dict

from .base import IntelligenceModule, ModulePhase


class IntelligenceRegistry:
    """Discover, load, and manage intelligence modules."""
    
    def __init__(self, config=None, ui=None):
        self.config = config or {}
        self.ui = ui
        self.modules: Dict[str, IntelligenceModule] = {}
        self.logger = logging.getLogger("neuralcode.intelligence")
        self._load_built_in_modules()
        self._load_user_plugins()
    
    def _load_built_in_modules(self):
        """Discover and instantiate built-in modules."""
        built_in = [
            "tool_optimizer",
            "budget_forecaster",
            "pressure_response",
            "smart_tools",
            "teaching_mode",
        ]
        
        for module_name in built_in:
            try:
                mod = importlib.import_module(f"neuralcode.intelligence.{module_name}")
                
                # Find the IntelligenceModule subclass
                for name in dir(mod):
                    obj = getattr(mod, name)
                    if (isinstance(obj, type) and 
                        issubclass(obj, IntelligenceModule) and 
                        obj is not IntelligenceModule):
                        
                        instance = obj(config=self.config, ui=self.ui)
                        self.modules[module_name] = instance
                        self.logger.debug(f"Loaded: {instance}")
            except Exception as e:
                self.logger.warning(f"Failed to load {module_name}: {e}")
    
    def _load_user_plugins(self):
        """Load user-provided plugins from ~/.agents/plugins/."""
        plugins_dir = Path.home() / ".agents" / "plugins"
        if not plugins_dir.exists():
            return
        
        for plugin_file in plugins_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(
                    f"plugin_{plugin_file.stem}", 
                    plugin_file
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                for name in dir(mod):
                    obj = getattr(mod, name)
                    if (isinstance(obj, type) and 
                        issubclass(obj, IntelligenceModule) and 
                        obj is not IntelligenceModule):
                        
                        instance = obj(config=self.config, ui=self.ui)
                        key = f"plugin_{plugin_file.stem}"
                        self.modules[key] = instance
                        self.logger.debug(f"Loaded plugin: {instance}")
            except Exception as e:
                self.logger.warning(f"Failed to load plugin {plugin_file}: {e}")
    
    def enable(self, name: str):
        """Enable a module."""
        if name in self.modules:
            self.modules[name].enabled_by_default = True
    
    def disable(self, name: str):
        """Disable a module."""
        if name in self.modules:
            self.modules[name].enabled_by_default = False
    
    def get_for_phase(self, phase: ModulePhase) -> List[IntelligenceModule]:
        """Get all enabled modules for a given phase."""
        return [
            m for m in self.modules.values()
            if m.enabled_by_default and m.phase == phase and m.can_run()
        ]
    
    def list_all(self) -> str:
        """Return human-readable module list."""
        lines = ["Intelligence Modules:"]
        for name, mod in self.modules.items():
            status = "✓" if mod.enabled_by_default else "✗"
            lines.append(f"  {status} {name}: {mod.description}")
        return "\n".join(lines)
```

---

## Step 3: Update Config for Feature Flags

### `neuralcode/config.py` (UPDATED)

```python
"""Settings: environment, ~/.agents/env, and ~/.agents/config.yaml."""

import os
from pathlib import Path
import yaml

ENV_FILE = Path.home() / ".agents" / "env"
CONFIG_FILE = Path.home() / ".agents" / "config.yaml"

# Load environment
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

BASE_URL = os.environ["BASE_URL"]
API_KEY = os.environ["API_KEY"]
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash")

# Context window sizing
CONTEXT_WINDOW = int(os.environ.get("CONTEXT_WINDOW", 128_000))
COMPACT_AT = 0.85  # compact once prompt crosses this % of window
COMPACT_TO = 0.35  # and cut back to this much

# Intelligence features (loaded from ~/.agents/config.yaml)
INTELLIGENCE_CONFIG = {
    "mode": "intelligent",           # intelligent, minimal, or teaching
    "enabled_modules": [
        "tool_optimizer",
        "budget_forecaster",
        "pressure_response",
        "smart_tools",
    ],
    "disabled_modules": [],
    "tool_optimizer": {
        "enabled": True,
        "aggressive": False,  # More aggressive rewrites
    },
    "budget_forecaster": {
        "enabled": True,
        "verbose": False,     # Show token forecasts
    },
    "pressure_response": {
        "enabled": True,
        "auto_compact": True, # Auto-compact at high pressure
    },
    "teaching_mode": {
        "enabled": False,     # Enabled with --teach flag
        "log_level": "DEBUG",
    },
}

# Load from YAML if it exists
if CONFIG_FILE.exists():
    try:
        yaml_config = yaml.safe_load(CONFIG_FILE.read_text())
        if yaml_config:
            INTELLIGENCE_CONFIG.update(yaml_config)
    except Exception as e:
        print(f"Warning: Failed to load {CONFIG_FILE}: {e}")

# CLI override: check for --teach, --mode, etc. in sys.argv
# (actual parsing happens in agent.py)
```

### Sample `~/.agents/config.yaml`

```yaml
# Cortex-Agent Intelligence Configuration

# Mode: intelligent (all modules), minimal (core only), teaching (with explanations)
mode: intelligent

# Enabled modules by default
enabled_modules:
  - tool_optimizer
  - budget_forecaster
  - pressure_response
  - smart_tools

# Modules to disable
disabled_modules: []

# Per-module configuration
tool_optimizer:
  enabled: true
  # Aggressively rewrite bash → read_file even if not perfect
  aggressive: false

budget_forecaster:
  enabled: true
  # Show token forecasts before each LLM call
  verbose: false

pressure_response:
  enabled: true
  # Automatically trigger /compact at high pressure (>90%)
  auto_compact: true

teaching_mode:
  enabled: false
  # Only enabled with --teach CLI flag
  log_level: DEBUG

# Session settings
session:
  # Store cache of tool call results for dedup
  enable_tool_cache: true
  cache_dir: ~/.agents/cache

# Skills directory
skills:
  user_dir: ~/.agents/skills
```

---

## Step 4: Integrate into Agent Main Loop

### `neuralcode/agent.py` (UPDATED)

```python
import argparse
from . import commands, compact, history, session
from .context import reminder
from .llm import SYSTEM_PROMPT, call_llm
from . import sandbox
from .todos import active_form
from .tools import execute
from .ui import ui
from .intelligence.registry import IntelligenceRegistry
from .intelligence.base import ModulePhase
from . import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="continue the last session")
    parser.add_argument("--debug", action="store_true", help="show the raw model response")
    parser.add_argument("--teach", action="store_true", help="verbose narration of agent decisions")
    parser.add_argument("--mode", choices=["intelligent", "minimal", "teaching"],
                        default=config.INTELLIGENCE_CONFIG.get("mode", "intelligent"),
                        help="agent mode")
    parser.add_argument("--list-modules", action="store_true", help="show available modules and exit")
    cli = parser.parse_args()
    
    # Initialize intelligence registry
    config.INTELLIGENCE_CONFIG["mode"] = cli.mode
    if cli.teach:
        config.INTELLIGENCE_CONFIG["mode"] = "teaching"
        config.INTELLIGENCE_CONFIG["teaching_mode"]["enabled"] = True
    
    registry = IntelligenceRegistry(config=config.INTELLIGENCE_CONFIG, ui=ui)
    
    if cli.list_modules:
        ui.console.print(registry.list_all())
        return
    
    ui.banner(sandbox.name())
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if cli.resume:
        saved = session.all_sessions()
        if saved:
            messages = session.open_session(saved[0]["id"])
            history.strip(messages)
            ui.resumed(messages)
            ui.replay(messages)
    
    while True:
        # PRE_LLM phase: run modules that intercept before LLM call
        for module in registry.get_for_phase(ModulePhase.PRE_LLM):
            result = module.execute(messages=messages, config=config)
            if result:  # Module might return a message to inject
                messages.append(result)
        
        user_input = ui.ask()
        if not user_input:
            break
        
        if user_input.startswith("/"):
            messages = commands.handle(user_input, messages)
            session.save(messages)
            continue
        
        messages.append({"role": "user", "content": user_input})
        
        while True:
            # CONTEXT_CHECK phase: run modules that monitor pressure
            for module in registry.get_for_phase(ModulePhase.CONTEXT_CHECK):
                result = module.execute(messages=messages, config=config)
                if result:
                    messages.append(result)
            
            injection = reminder()
            ui.injection(injection["content"])
            
            if history.fit(messages):
                ui.note("dropped old tool output to make this request fit")
            
            with ui.working(active_form()):
                message, usage = call_llm(messages + [injection])
            
            messages.append(message.model_dump(exclude_none=True))
            session.save(messages)
            ui.usage(usage)
            
            if cli.debug:
                ui.debug(message.model_dump(exclude_none=True))
            
            if message.content:
                ui.agent(message.content)
            
            if not message.tool_calls:
                break
            
            for tool_call in message.tool_calls:
                # TOOL_INTERCEPT phase: modules can optimize tool calls
                optimized_call = tool_call
                for module in registry.get_for_phase(ModulePhase.TOOL_INTERCEPT):
                    result = module.execute(tool_call=optimized_call, config=config)
                    if result:
                        optimized_call, reason = result
                        if reason:
                            ui.note(f"🔧 {reason}")
                
                args, result = execute(optimized_call)
                ui.tool(optimized_call.function.name, args, result)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                session.save(messages)
                
                # POST_TOOL phase: modules run after tool execution
                for module in registry.get_for_phase(ModulePhase.POST_TOOL):
                    module.execute(messages=messages, result=result, config=config)
        
        history.sweep()
        history.strip(messages)
        
        if compact.needed(usage):
            messages = commands.compact(messages)
    
    ui.summary()


if __name__ == "__main__":
    main()
```

---

## Step 5: Create Installation Script

### `scripts/install.sh` (NEW)

```bash
#!/bin/bash
set -e

echo "🧠 Installing Cortex-Agent with Intelligence Modules"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version detected"

# Install package (editable or from PyPI)
if [ -f "pyproject.toml" ]; then
    echo "📦 Installing from local source..."
    pip install -e .
else
    echo "📦 Installing from PyPI..."
    pip install neuralcode
fi

# Create config directories
mkdir -p ~/.agents/skills ~/.agents/plugins ~/.agents/cache
echo "✓ Created ~/.agents/ directory structure"

# Copy default config if not exists
if [ ! -f ~/.agents/config.yaml ]; then
    echo "📝 Creating default config.yaml..."
    cp config.yaml.example ~/.agents/config.yaml || cat > ~/.agents/config.yaml << 'EOF'
mode: intelligent

enabled_modules:
  - tool_optimizer
  - budget_forecaster
  - pressure_response
  - smart_tools

disabled_modules: []

tool_optimizer:
  enabled: true
  aggressive: false

budget_forecaster:
  enabled: true
  verbose: false

pressure_response:
  enabled: true
  auto_compact: true

teaching_mode:
  enabled: false
  log_level: DEBUG

session:
  enable_tool_cache: true
  cache_dir: ~/.agents/cache
EOF
fi

# Create sample env file template if not exists
if [ ! -f ~/.agents/env ]; then
    echo "📝 Creating .env template..."
    cat > ~/.agents/env << 'EOF'
# API Configuration
BASE_URL=https://api.deepseek.com/v1
API_KEY=sk-your-key-here
MODEL=deepseek/deepseek-v4-flash

# Context window (tokens)
CONTEXT_WINDOW=128000

# Optional: Override defaults
# COMPACT_AT=0.85
# COMPACT_TO=0.35
EOF
    echo "⚠️  Update ~/.agents/env with your API credentials"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.agents/env with your API credentials"
echo "  2. Run: neuralcode --list-modules"
echo "  3. Start: neuralcode"
echo ""
echo "Help:"
echo "  neuralcode --help"
echo "  neuralcode --teach              (show optimization decisions)"
echo "  neuralcode --mode=minimal       (disable intelligence modules)"
echo "  neuralcode --list-modules       (show loaded modules)"
```

---

## Step 6: Provide Update Mechanism

### `neuralcode/update.py` (NEW)

```python
"""Check for updates and manage module versions."""

import subprocess
import sys
from packaging import version as pkg_version


def check_for_updates():
    """Check PyPI for newer version."""
    try:
        result = subprocess.run(
            ["pip", "index", "versions", "neuralcode"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            # Parse latest version from output
            import re
            match = re.search(r"Available versions: ([\d.]+)", result.stdout)
            if match:
                latest = match.group(1)
                import neuralcode
                current = neuralcode.__version__
                
                if pkg_version.parse(latest) > pkg_version.parse(current):
                    return latest
    except Exception:
        pass
    
    return None


def suggest_update():
    """Show update prompt to user."""
    latest = check_for_updates()
    if latest:
        print(f"""
⚠️  Update available: {latest}

Intelligence modules, bug fixes, and performance improvements are ready.

To update:
  pip install --upgrade neuralcode
  neuralcode --list-modules

Changes: github.com/PyrateGFXProductions/cortex-agent/releases
""")
        return True
    return False
```

---

## Step 7: Distribution Timeline

### Phase 1: Beta Release (v0.2.0)
```
Week 1-2: Merge intelligence modules into main
         - Create PR with all new modules
         - Add tests for each module
         - Document in README

Week 3:   PyPI Release
         - Tag v0.2.0
         - Push to PyPI
         - Announce on channels
```

### Phase 2: User Feedback (v0.2.1-0.2.x)
```
- Monitor usage patterns
- Collect optimization opportunities
- Fine-tune module parameters
- Add telemetry (opt-in)
```

### Phase 3: Stable Release (v0.3.0)
```
- Make intelligence default (mode: intelligent)
- Add community plugins framework
- Create marketplace for skills
```

---

## Installation Variants

### Users with pip
```bash
pip install neuralcode
# Automatically gets intelligence modules

# Or specific version
pip install neuralcode==0.2.0
```

### Users with homebrew (macOS)
```bash
brew install neuralcode
# Builds from source, includes intelligence
```

### Users with Docker
```dockerfile
FROM python:3.11
RUN pip install neuralcode
ENTRYPOINT ["neuralcode"]
```

### Users who develop
```bash
git clone https://github.com/PyrateGFXProductions/cortex-agent
cd cortex-agent
pip install -e .
neuralcode --teach
```

---

## User Control & Transparency

### Enable/Disable per Session
```bash
# Use intelligent mode (default)
neuralcode

# Disable all intelligence
neuralcode --mode=minimal

# Show all decisions
neuralcode --teach

# Show what's loaded
neuralcode --list-modules

# Disable specific module
neuralcode --disable=tool_optimizer
```

### Configuration File
Edit `~/.agents/config.yaml`:
```yaml
enabled_modules:
  - tool_optimizer        # Keep
  - pressure_response     # Keep
  # - budget_forecaster  # Disabled (commented out)
```

### Per-Command Override
```bash
# Temporarily enable teaching mode
neuralcode --teach --mode=intelligent

# Use minimal, but list modules
neuralcode --mode=minimal --list-modules
```

---

## Telemetry & Privacy

### Opt-in Telemetry (v0.3+)
Users can optionally share:
- Module execution times
- Token savings achieved
- Error rates

All data is:
- Anonymized (no session content)
- Aggregated
- Optional (default: off)

Enable:
```yaml
telemetry:
  enabled: false              # Opt-in
  send_module_metrics: false
  send_token_savings: false
```

---

## Support & Documentation

### In-Agent Help
```bash
neuralcode --help                    # Main help
neuralcode --help-intelligence       # Module docs
neuralcode --teach-errors            # Error recovery gallery
```

### Online Documentation
```
https://github.com/PyrateGFXProductions/cortex-agent/wiki/Intelligence-Modules
https://github.com/PyrateGFXProductions/cortex-agent/wiki/Configuration
https://github.com/PyrateGFXProductions/cortex-agent/wiki/Custom-Plugins
```

### Community Plugins
```
https://github.com/cortex-agent-plugins/   (community-contributed)
```

---

## Rollback Strategy

If a module causes issues:

```bash
# Disable it temporarily
neuralcode --disable=tool_optimizer

# Or disable all
neuralcode --mode=minimal

# Downgrade to stable
pip install neuralcode==0.1.0
```

Config to disable permanently:
```yaml
disabled_modules:
  - tool_optimizer
```

---

## Success Metrics

After global distribution, measure:

| Metric | Target |
|--------|--------|
| Token waste reduction | 30-40% |
| Avg context usage (start → end) | 60% → 45% |
| Compaction frequency | 5/session → 2/session |
| Users enabling teaching mode | >10% |
| Community plugins | >5 in first month |

---

## Summary

**The distribution strategy:**

1. ✅ **Package** modules into `neuralcode/intelligence/`
2. ✅ **Register** them via `IntelligenceRegistry`
3. ✅ **Configure** via `~/.agents/config.yaml`
4. ✅ **Deploy** to PyPI as part of main package
5. ✅ **Control** via CLI flags (`--teach`, `--mode`, `--list-modules`)
6. ✅ **Update** automatically via pip
7. ✅ **Extend** via user plugins in `~/.agents/plugins/`

**Result:** Every user automatically gets intelligence improvements on `pip install neuralcode`, but can opt out or customize at will.
