"""MCP server: expose cortex-agent tools to any MCP-compatible client.

Supported clients: Claude Desktop, Cursor, Windsurf, VS Code (via Continue),
and any other client that speaks the Model Context Protocol.

Tools exposed:
  bash        - run a shell command
  read_file   - read a file by path
  write_file  - create or overwrite a file
  str_replace  - make a targeted text edit in a file
  read_skill  - load a skill by name from ~/.agents/skills/

Deliberately excluded:
  task        - requires LLM API credentials (awkward to configure per-client)
  write_todos - internal session state; meaningless outside the agent loop

Setup (add to your MCP client config):

  Claude Desktop  ~/Library/Application Support/Claude/claude_desktop_config.json
  Cursor          ~/.cursor/mcp.json
  Windsurf        ~/.codeium/windsurf/mcp_settings.json

  {
    "mcpServers": {
      "cortex-agent": {
        "command": "cortex-agent-mcp"
      }
    }
  }

Install first:
  pip install "cortex-agent[mcp]"
  # or, from source:
  pip install -e ".[mcp]"
"""

from mcp.server.fastmcp import FastMCP

# Import tool functions directly — deliberately does NOT import config.py,
# which requires BASE_URL/API_KEY env vars that MCP clients don't need.
from .history import cap
from .sandbox import run as sandbox_run
from .skills import read_skill as _read_skill
from .permissions import check

import json
import subprocess


mcp = FastMCP(
    "cortex-agent",
    instructions=(
        "A set of coding tools: run shell commands, read/write/edit files, "
        "and load skill instruction files. "
        "bash output is capped at 10,000 characters; use head/tail/grep for large outputs."
    ),
)


def _gate(name: str, args: dict) -> str | None:
    """Run the same permission check the interactive CLI uses, but fail closed
    on 'ask' — an MCP client has no human to prompt, so anything that would
    interrupt the CLI is refused here rather than silently allowed.
    Returns None when allowed, or a 'Blocked by policy' message."""
    action, reason = check(name, args)
    if action == "allow":
        return None
    return f"Blocked by policy: {reason}"


@mcp.tool()
def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr.

    Output is capped at 10,000 characters. For large outputs, use
    head, tail, or grep to page through the result.
    """
    blocked = _gate("bash", {"command": command})
    if blocked:
        return blocked
    try:
        result = sandbox_run(command)
        return cap((result.stdout + result.stderr) or "(no output)")
    except subprocess.TimeoutExpired as expired:
        return (
            f"Timed out after {expired.timeout}s and was killed. "
            "Narrow it down — search inside the working directory rather than /."
        )


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file and return its contents.

    Output is capped at 10,000 characters.
    """
    try:
        with open(path) as f:
            return cap(f.read())
    except OSError as e:
        return f"Error: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create a file, or overwrite it if it already exists."""
    blocked = _gate("write_file", {"path": path})
    if blocked:
        return blocked
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {path}"
    except OSError as e:
        return f"Error: {e}"


@mcp.tool()
def str_replace(path: str, old_str: str, new_str: str, allow_multi_edit: bool = False) -> str:
    """Replace exact text in a file.

    old_str must appear exactly once unless allow_multi_edit is true.
    Include surrounding lines to make the match unique.
    """
    blocked = _gate("str_replace", {"path": path})
    if blocked:
        return blocked
    try:
        with open(path) as f:
            content = f.read()
    except OSError as e:
        return f"Error: {e}"

    first = content.find(old_str)
    if first == -1:
        return f"Error: old_str was not found in {path}"

    if not allow_multi_edit:
        second = content.find(old_str, first + len(old_str))
        if second != -1:
            count = content.count(old_str)
            return (
                f"Error: old_str matches {count} times in {path}. "
                "Add surrounding lines to make it unique, "
                "or set allow_multi_edit to true to replace all."
            )
        new_content = content[:first] + new_str + content[first + len(old_str):]
        try:
            with open(path, "w") as f:
                f.write(new_content)
        except OSError as e:
            return f"Error: {e}"
        return f"Replaced 1 match in {path}"

    count = content.count(old_str)
    try:
        with open(path, "w") as f:
            f.write(content.replace(old_str, new_str))
    except OSError as e:
        return f"Error: {e}"
    return f"Replaced {count} match(es) in {path}"


@mcp.tool()
def read_skill(name: str) -> str:
    """Load a skill by name and return its full instructions.

    Skills are markdown files in ~/.agents/skills/ or .agents/skills/
    relative to the current working directory.
    """
    return _read_skill(name)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
