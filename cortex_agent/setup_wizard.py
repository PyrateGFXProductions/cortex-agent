"""First-run setup wizard.

Called from agent.main() before anything that needs BASE_URL or API_KEY.
If the credentials are already present (env file or environment), this is a
no-op. Otherwise it walks the user through picking a provider and entering an
API key, then figures out which model to use — never by hardcoding one: for a
local backend it discovers the models already on the machine (e.g. Ollama) and
suggests them, and for a remote provider it asks. It then writes ~/.agents/env
so subsequent runs skip the wizard entirely.
"""

import getpass
import os
import shutil
import subprocess
from pathlib import Path

ENV_FILE = Path.home() / ".agents" / "env"

PROVIDERS = {
    "1": (
        "OpenRouter  (recommended — one key, access to every model)",
        "https://openrouter.ai/api/v1",
        "https://openrouter.ai/keys",
    ),
    "2": (
        "OpenAI  (GPT-4o, o3, etc.)",
        "https://api.openai.com/v1",
        "https://platform.openai.com/api-keys",
    ),
    "3": (
        "Local  (Ollama / LM Studio — no API key needed)",
        "http://localhost:11434/v1",
        None,
    ),
    "4": (
        "Other  (enter your own base URL)",
        None,
        None,
    ),
}


def _already_configured() -> bool:
    """Return True if BASE_URL and API_KEY are already available."""
    # config.py already loaded the env file into os.environ at import time,
    # so we just check the environment directly. The installer's placeholder
    # key is not a real credential - treat it as unconfigured so the wizard
    # runs instead of silently failing every request with an auth error.
    key = os.environ.get("API_KEY", "").strip()
    return bool(os.environ.get("BASE_URL")) and bool(key) and key != "sk-or-your-key-here"


def _print_banner():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        console = Console()
        title = Text("Welcome to cortex-agent", style="bold cyan")
        subtitle = Text("Let's get you set up in 60 seconds", style="dim")
        console.print()
        console.print(Panel.fit(
            f"{title}\n{subtitle}",
            border_style="cyan",
            padding=(1, 4),
        ))
        console.print()
    except Exception:
        print("\n=== Welcome to cortex-agent ===")
        print("Let's get you set up in 60 seconds.\n")


def _ok(msg: str):
    try:
        from rich.console import Console
        Console().print(f"[bold green]✓[/]  {msg}")
    except Exception:
        print(f"✓  {msg}")


def _prompt(label: str, default: str = "") -> str:
    """Read a line with an optional default shown in brackets."""
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{label}{suffix} > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    return value or default


def _secret(label: str) -> str:
    """Read a secret (hidden) value — retries until non-empty."""
    while True:
        try:
            value = getpass.getpass(f"{label} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if value:
            return value
        print("  API key cannot be empty. Try again.")


def discover_local_models() -> list[str]:
    """Return the model names a local backend already has, or [] if unknown.

    The demo client talks to any OpenAI-compatible endpoint. We never hardcode
    which model to use — for a local backend we list what is actually present
    on the machine (Ollama) and let the user pick, rather than guessing a name
    that may not be pulled yet.
    """
    if not shutil.which("ollama"):
        return []
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = []
    for line in out.splitlines()[1:]:  # skip the header row
        fields = line.split()
        if fields and ":" in fields[0]:
            names.append(fields[0])
    return names


def _choose_model(provider: str) -> str:
    """Pick a model without ever assuming one. Local backends get their own
    discovered models suggested; remote backends are asked directly."""
    local = discover_local_models() if provider == "3" else []
    if local:
        _ok(f"Found {len(local)} model(s) already on this machine")
        for i, name in enumerate(local, 1):
            print(f"  {i}  {name}")
        print(f"  m  enter a different model name")
        raw = _prompt("Choose a model", default=local[0])
        if raw.strip().lower() != "m":
            if raw.isdigit() and 1 <= int(raw) <= len(local):
                return local[int(raw) - 1]
            for name in local:
                if name == raw.strip():
                    return name

    while True:
        model = _prompt("Model name").strip()
        if model:
            return model
        print("  A model name is required — it must match an endpoint.")


def _write_env(base_url: str, api_key: str, model: str):
    """Write (or overwrite) ~/.agents/env."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# cortex-agent configuration\n"
        f"BASE_URL={base_url}\n"
        f"API_KEY={api_key}\n"
        f"MODEL={model}\n"
        "\n"
        "# Optional\n"
        "# CONTEXT_WINDOW=128000\n"
    )
    ENV_FILE.write_text(content, encoding="utf-8")

    # Inject into the current process so the agent starts without a restart.
    os.environ["BASE_URL"] = base_url
    os.environ["API_KEY"] = api_key
    os.environ["MODEL"] = model


def ensure_configured():
    """Run the wizard if credentials are missing; no-op otherwise."""
    if _already_configured():
        return

    _print_banner()

    # --- Provider selection ---
    print("Which API provider would you like to use?\n")
    for key, (label, *_) in PROVIDERS.items():
        print(f"  {key}  {label}")
    print()
    choice = _prompt("Your choice", default="1")
    if choice not in PROVIDERS:
        choice = "1"

    label, base_url, key_url = PROVIDERS[choice]

    # --- Base URL (custom provider) ---
    if base_url is None:
        base_url = _prompt("Base URL (e.g. https://api.example.com/v1)")
        if not base_url:
            print("Base URL is required. Run cortex-agent again to retry.")
            raise SystemExit(1)

    # --- API key ---
    if choice == "3":
        # Local — no key needed; use a placeholder that OpenAI SDK accepts.
        api_key = "local"
        _ok("Local provider — no API key needed")
    else:
        if key_url:
            print(f"\n  Get your API key at: {key_url}\n")
        api_key = _secret("API key (hidden)")

    # --- Model (discovered for local backends, never hardcoded) ---
    model = _choose_model(choice)

    # --- Write and confirm ---
    _write_env(base_url, api_key, model)
    print()
    _ok(f"Saved to {ENV_FILE}")
    _ok("Ready to go!")
    print()
