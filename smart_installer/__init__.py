"""cortex-agent smart enhancement patcher.

A client-agnostic tool that implements the cortex-agent context-window
efficiency patterns into any AI coding agent's source tree (opencode,
hermes, aider, claude-code, or a custom client).

The six patterns (see EFFICIENCY_PATTERNS.md):

  1. Locked prefix + late injection
  2. Three-tier tool output degradation (cap / strip / drop)
  3. Compaction with prefix rebuild
  4. Isolated subagents
  5. File staleness detection
  6. Hardware-aware automatic configuration

Each pattern ships as a probe (does this client already have it? where are
the integration points?) plus either automatic source edits or precise
porting guidance for manual application. Known clients get a fully verified
recipe (see recipes/opencode.py); unknown clients are matched by language
and structure.
"""

__version__ = "0.3.0"