#!/usr/bin/env python3
"""smart-installer — apply cortex-agent efficiency patterns to any AI client.

Usage (from repo root):

    # inspect a client source tree (no changes)
    python -m smart_installer path/to/opencode

    # dry-run: show the exact edits for every pattern a recipe covers
    python -m smart_installer path/to/opencode --apply --dry-run

    # actually apply the recipe (creates a timestamped backup dir)
    python -m smart_installer path/to/opencode --apply

    # probe only one pattern / show guidance for all
    python -m smart_installer path/to/aider --probe-only
    python -m smart_installer path/to/client --guide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.target import Target
from .engine import Engine
from .patterns.library import REGISTRY, BY_ID
from .recipes import RECIPES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smart-installer",
        description="Apply cortex-agent efficiency patterns to any AI coding client source tree.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("target", help="path to the client source tree to inspect/patch")
    p.add_argument("--apply", action="store_true", help="apply a known client recipe (default: probe only)")
    p.add_argument("--dry-run", action="store_true", help="with --apply: show edits without writing (off by default — a bare --apply writes)")
    p.add_argument("--pattern", action="append", choices=sorted(BY_ID), help="only run these patterns (repeatable)")
    p.add_argument("--probe-only", action="store_true", help="only assess pattern status, no edits/recipe")
    p.add_argument("--guide", action="store_true", help="print porting instructions per pattern")
    p.add_argument("--force", action="store_true", help="allow editing a tree that is not a git checkout")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

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

        # Safety: --apply without --dry-run writes. Pass --dry-run to preview.
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
        print("Review the edits, then build/test the client. Re-reun this tool to confirm 'applied' status.")
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


if __name__ == "__main__":
    sys.exit(main())