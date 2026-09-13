#!/usr/bin/env python3
"""smart-installer — two things, no model hardcoding.

This tool configures the cortex-agent *efficiency patterns*. It never installs
or chooses an LLM model — a client already has its own endpoint and model, and
cortex-agent only changes how that client handles information.

  1. demo  — set up the standalone demo client (cortex-agent). This is a fully
     functional reference client that demonstrates the patterns. Its setup
     *discovers* models already on the machine (e.g. Ollama) and suggests them
     rather than hardcoding one.
  2. patch — apply the six efficiency patterns to an existing client's source
     tree (opencode, aider, hermes, …). The client's model and settings are
     left untouched; only the pattern wiring is edited.

Usage (from repo root):

    python -m smart_installer                            # interactive menu
    python -m smart_installer demo                       # option 1
    python -m smart_installer patch path/to/opencode     # option 2, probe
    python -m smart_installer patch path/to/opencode --apply --dry-run
    python -m smart_installer patch path/to/opencode --apply
"""

from __future__ import annotations

import argparse
import sys

from .core.target import Target
from .engine import Engine
from .patterns.library import REGISTRY, BY_ID
from .recipes import RECIPES


# ----------------------------------------------------------------- option 1

def run_demo() -> int:
    """Set up the standalone demo client. Discovers models, never hardcodes."""
    try:
        from cortex_agent.setup_wizard import ensure_configured
    except ImportError:
        print(
            "error: cannot find the demo client (cortex_agent) in this tree. "
            "Run from the repo root.",
            file=sys.stderr,
        )
        return 1

    print("==> cortex-agent demo client setup")
    ensure_configured()

    print()
    print("Demo client configured. Run it from inside any project directory:")
    print("    uv run cortex-agent        # or:  python -m cortex_agent")
    print()
    print("Install it system-wide with:")
    print("    uv tool install .[mcp]     # or:  pip install .")
    return 0


# ----------------------------------------------------------------- option 2

def add_patch_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", help="path to the client source tree to inspect/patch")
    p.add_argument("--apply", action="store_true", help="apply a known client recipe (default: probe only)")
    p.add_argument("--dry-run", action="store_true", help="with --apply: show edits without writing (off by default — a bare --apply writes)")
    p.add_argument("--pattern", action="append", choices=sorted(BY_ID), help="only run these patterns (repeatable)")
    p.add_argument("--probe-only", action="store_true", help="only assess pattern status, no edits/recipe")
    p.add_argument("--guide", action="store_true", help="print porting instructions per pattern")
    p.add_argument("--force", action="store_true", help="allow editing a tree that is not a git checkout")


def run_patch(args: argparse.Namespace) -> int:
    try:
        target = Target(args.target)
    except NotADirectoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    patterns = REGISTRY if not args.pattern else [BY_ID[i] for i in args.pattern]

    # ---- probe / report -------------------------------------------------
    print(f"Target: {target.describe()}")
    print()
    print("EFFICIENCY PATTERN STATUS")
    for p in patterns:
        a = p.assess(target)
        print(f"  [{a.status:8}] {p.name}")
        if a.reason:
            print(f"             {a.reason}")
        for f in a.findings[:4]:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"             @ {loc}  {(f.note or f.evidence)[:90]}")

    if args.guide:
        print()
        print("PORTING GUIDANCE")
        for p in patterns:
            print(f"  === {p.name} ===")
            for line in p.guide(target).splitlines():
                print("  " + line)
            print()

    if args.probe_only:
        return 0

    # ---- recipe apply ----------------------------------------------------
    if args.apply:
        recipe_fn = RECIPES.get(target.client)
        if recipe_fn is None:
            print()
            print(f"error: no recipe for client {target.client!r}. Known recipes: {sorted(RECIPES)}.", file=sys.stderr)
            print("Run without --apply to get porting guidance you can apply by hand.", file=sys.stderr)
            return 1

        engine = Engine(target, dry_run=True, force=args.force)
        reason = engine.ensure_safe()
        if reason and not args.force:
            print(f"\nrefusing: {reason}", file=sys.stderr)
            print("Pass --force to edit anyway (not recommended outside a git checkout).", file=sys.stderr)
            return 1

        plan = recipe_fn(target)
        print()
        print(f"RECIPE: {plan.note}")
        print(f"  {len(plan.edits)} edits; DRY-RUN (preview only)" if args.dry_run else f"  {len(plan.edits)} edits; WRITING TO DISK")

        if args.dry_run:
            print("\n" + engine.diff_of_plan(plan))
            print()
            print("Dry run only. Re-run with `--apply` and no `--dry-run` to write the changes.")
            return 0

        engine.dry_run = False
        result = engine.apply_plan(plan)
        print()
        for e in result.edits:
            print(f"  [{e.status:9}] {e.file}  {e.note}")
        print()
        applied = sum(1 for e in result.edits if e.status == "applied")
        skipped = sum(1 for e in result.edits if e.status == "skipped")
        problem = sum(1 for e in result.edits if e.status in ("missing", "ambiguous", "file not found"))
        print(f"applied={applied} already-present={skipped} needs-manual={problem}")
        if engine.backup_dir:
            print(f"backup: {engine.backup_dir}")
        print("Review the edits, then build/test the client. Re-run this tool to confirm 'applied' status.")
        return 0

    # ---- no recipe, no --apply: give next-step hints ---------------------
    print()
    print("Not patching. To apply:")
    print("  1. Run with --guide to read porting instructions per pattern.")
    print("  2. If a recipe exists for this client, run with --apply (dry-run first).")
    if target.client in RECIPES:
        print(f"  (a recipe exists for {target.client!r}: add --apply)")
    else:
        print(f"  (no recipe yet for {target.client!r}; add one in smart_installer/recipes/__init__.py)")
    return 0


# ------------------------------------------------------------ dispatch

def interactive_menu() -> int:
    print("cortex-agent smart installer")
    print()
    print("What would you like to do?")
    print("  1. Set up the standalone demo client (cortex-agent)")
    print("  2. Apply efficiency patterns to an existing client")
    print()
    try:
        choice = input("Choose [1/2] > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    if choice == "1":
        return run_demo()

    if choice == "2":
        try:
            path = input("Path to the client source tree > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not path:
            print("No path given.", file=sys.stderr)
            return 1
        return run_patch(argparse.Namespace(target=path, apply=False, dry_run=False, pattern=None, probe_only=False, guide=False, force=False))

    print("Nothing selected.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smart-installer",
        description="Apply cortex-agent efficiency patterns, or set up the demo client. Never hardcodes a model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("demo", help="set up the standalone demo client (discovers local models)")
    add_patch_args(sub.add_parser("patch", help="apply efficiency patterns to an existing client"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return run_demo()
    if args.command == "patch":
        return run_patch(args)
    return interactive_menu()


if __name__ == "__main__":
    sys.exit(main())