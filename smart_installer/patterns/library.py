"""The six efficiency patterns as client-agnostic probes.

Each pattern's `assess()` greps a target tree for tell-tale integration
markers and reports whether the enhancement is applied, absent, or partial,
plus where the wiring points are.  `guide()` explains exactly what to change
for the detected language, quoting the reference implementation from
cortex_agent/.  This is the plugin API: subclasses of `Pattern` in this
module, registered in `REGISTRY`, are what the engine runs.
"""

from __future__ import annotations

from .base import Assessment, EditPlan, Finding, Pattern


class LockedPrefixAndLateInjection(Pattern):
    """Patch 1: never mutate the cached prefix; inject env context at send time."""

    id = "locked_prefix_late_injection"
    name = "Locked prefix + late injection"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        # Applied markers: an injection builder exists and env info was
        # removed from the system prompt.
        inj = target.search("build_late_injection") + target.search("buildLateInjection")
        env_marker = target.search("<env>", limit_per_file=1)
        summary_marker = target.search("Summary:", limit_per_file=1)

        findings += inj + env_marker
        # Is env info baked into the system prompt still?
        prompt_files = target.find("prompt")
        baked_env: list[Finding] = []
        for rel in prompt_files:
            content = target.read(rel)
            if content and ("getcwd" in content or "PWD" in content or "git branch" in content):
                for i, line in enumerate(content.splitlines(), 1):
                    if "getcwd" in line or "PWD" in line or "git branch" in line:
                        baked_env.append(Finding(file=rel, line=i, evidence=line.strip()[:120], note="env info still in system prompt"))
                        break
        findings += baked_env

        applies = bool(inj) or bool(env_marker)
        if applies and not baked_env:
            status, reason = "applied", "injection builder + env marker found; prompt appears clean"
        elif applies:
            status, reason = "partial", "injection builder found but env info still baked into a prompt"
        elif baked_env:
            status, reason = "absent", "env info baked into system prompt; no injection builder"
        else:
            status, reason = "absent", "no injection builder found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        prompt_files = ", ".join(target.find("prompt")[:4]) or "the system-prompt builder"
        loop_files = target.search("completions.create", limit_per_file=1)
        loop = ", ".join(f.file for f in loop_files[:3]) or "the agent turn loop"
        return (
            f"Target: {lang} client. Prompt lives in: {prompt_files}.\n"
            f"LLM call site (agent loop): {loop}.\n"
            "1. Remove dynamic env info (cwd, date, git branch, todos) from the system prompt.\n"
            "2. Add a `build_env_injection()` step that appends an ephemeral <env> message\n"
            f"   at send time each turn — never stored. Reference: cortex_agent/context.py::reminder().\n"
            "3. Track a locked-prefix length: everything up to and including the last 'Summary:'\n"
            "   assistant message is cached; never mutate it (see patterns docs)."
        )


class ToolOutputDegradation(Pattern):
    """Patch 2: cap -> strip -> drop tool outputs."""

    id = "tool_output_degradation"
    name = "Three-tier tool output degradation"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        cap = target.search("MaxOutputLength", limit_per_file=1)
        strip = target.search("[output trimmed:", limit_per_file=1) + target.search("StripToolResults", limit_per_file=1) + target.search("StubLength", limit_per_file=1)
        findings += cap + strip

        if cap and strip:
            status, reason = "applied", "cap constant and strip marker both found"
        elif cap or strip:
            status, reason = "partial", "cap or strip found, but not the full cap->strip->drop chain"
        else:
            status, reason = "absent", "no output-cap or strip logic found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        bash = ", ".join(target.find("bash")[:2]) or "the bash tool executor"
        view = ", ".join(target.find("view")[:2]) or "the file-view tool"
        return (
            f"Target: {lang} client. Tool executors to patch: {bash}, {view}.\n"
            "1. CAP: truncate tool stdout to ~10K chars at creation; spill the full output to\n"
            "   a temp file and note its path in the trimmed stub.\n"
            "2. STRIP: at end of each turn, reduce tool results to ~300-char stubs marked\n"
            "   '[output trimmed: N more chars]' (idempotent marker).\n"
            "3. DROP: before an LLM call, discard oldest tool results if still over budget.\n"
            "Reference: cortex_agent/history.py (cap/strip/drop) + cortex_agent/tools.py."
        )


class CompactionWithPrefixRebuild(Pattern):
    """Patch 3: summarize-and-rewind at a fill threshold."""

    id = "compaction_prefix_rebuild"
    name = "Compaction with prefix rebuild"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        compact = target.search("CompactAt", limit_per_file=1) + target.search("COMPACT_AT", limit_per_file=1)
        summarize = target.search("Summarize", limit_per_file=1) + target.search("summarize", limit_per_file=2)
        summary_marker = target.search("Summary:", limit_per_file=1)
        findings += compact + summarize + summary_marker

        if compact and summarize:
            status, reason = "applied", "compaction trigger + summarizer found"
        elif compact or summarize:
            status, reason = "partial", "compaction plumbing found but incomplete"
        else:
            status, reason = "absent", "no compaction trigger or summarizer found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        return (
            f"Target: {lang} client. Add compaction to the agent turn loop:\n"
            "1. Pick compact-at / compact-to fractions (defaults 0.85 / 0.35).\n"
            "2. When prompt_tokens > CONTEXT_WINDOW * compact_at, summarize all messages up to\n"
            "   a cut such that the tail fits in CONTEXT_WINDOW * compact_to.\n"
            "3. Rebuild: system + 'Summary: <handoff note>' + tail. The new locked prefix is\n"
            "   [system, summary]. Use a cheap secondary model/provider for the summary call.\n"
            "Reference: cortex_agent/compact.py::compact() + summarize()."
        )


class IsolatedSubagents(Pattern):
    """Patch 4: subagents run in fresh context with read-only tools, capped turns."""

    id = "isolated_subagents"
    name = "Isolated subagents (task tool)"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        max_turns = target.search("SubagentMaxTurns", limit_per_file=1) + target.search("maxTurns", limit_per_file=1) + target.search("MAX_TURNS", limit_per_file=1)
        read_only = target.search("read-only", limit_per_file=1) + target.search("readonly", limit_per_file=1) + target.search("READ_ONLY", limit_per_file=1)
        findings += max_turns + read_only

        if max_turns and read_only:
            status, reason = "applied", "subagent turn cap and read-only toolset found"
        elif max_turns or read_only:
            status, reason = "partial", "some subagent isolation found"
        else:
            status, reason = "absent", "no subagent isolation found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        task = ", ".join(target.find("task")[:3]) or "the task/subagent tool"
        return (
            f"Target: {lang} client. The subagent tool lives in: {task}.\n"
            "1. Create the subagent with an empty message history (system + user prompt only).\n"
            "2. Give it a read-only toolset: no bash/write/edit/patch/todos/subagent tools.\n"
            "3. Cap it to 12 turns; after that return a hard stop.\n"
            "4. Only the final text response crosses back to the parent.\n"
            "Reference: cortex_agent/subagent.py + the opencode task.go recipe."
        )


class FileStalenessDetection(Pattern):
    """Patch 5: warn when a read file changed since last read (os.stat mtime/size)."""

    id = "file_staleness_detection"
    name = "File staleness detection"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        tracker = target.search("filetrack", limit_per_file=2) + target.search("RecordRead", limit_per_file=1) + target.search("GetStaleWarning", limit_per_file=1)
        stat = target.search("os.Stat", limit_per_file=1) + target.search("st_mtime", limit_per_file=1) + target.search("ModTime", limit_per_file=1)
        findings += tracker + stat

        if tracker:
            status, reason = "applied", "file staleness tracker found"
        elif stat:
            status, reason = "partial", "file stats tracked, but no staleness warning path"
        else:
            status, reason = "absent", "no file-staleness tracking found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        view = ", ".join(target.find("view")[:2]) or "the file-read tool"
        return (
            f"Target: {lang} client. Hook into the read tool: {view}.\n"
            "1. Track (mtime, size) per read file via os.stat — O(1), no hashing.\n"
            "2. Each turn, diff the tracked stats against the live files.\n"
            "3. Inject a '<system-reminder>' with the stale list via the late injection.\n"
            "Reference: cortex_agent/context.py + internal/filetrack/tracker.go."
        )


class HardwareAwareConfig(Pattern):
    """Patch 6: detect GPU/RAM/CPU and apply optimal config defaults."""

    id = "hardware_aware_config"
    name = "Hardware-aware automatic configuration"
    tier = "guided"

    def assess(self, target) -> Assessment:
        findings: list[Finding] = []
        detect = target.search("applyHardwareDefaults", limit_per_file=1) + target.search("detect_hardware", limit_per_file=1) + target.search("HardwareInfo", limit_per_file=1) + target.search("GetProfile", limit_per_file=1)
        findings += detect

        if detect:
            status, reason = "applied", "hardware detection + profile logic found"
        else:
            status, reason = "absent", "no hardware detection found"
        return Assessment(self.id, status, reason, findings, self.tier)

    def guide(self, target) -> str:
        lang = target.languages[0] if target.languages else "unknown"
        return (
            f"Target: {lang} client. Add hardware detection at config load:\n"
            "1. Probe GPU (nvidia-smi / rocm-smi / wmic / system_profiler), RAM, CPU cores.\n"
            "2. Map to a profile: high_end >=24GB, mid_range 8-24GB, low_end <8GB, apple_silicon, cpu_only.\n"
            "3. Each profile sets defaults: context_window, CompactAt/CompactTo, tool cap/stub,\n"
            "   subagent turns, max tokens. Apply as defaults (user overrides win).\n"
            "Reference: EFFICIENCY_PATTERNS.md Pattern 6 + recipes/ HARDWARE_DETECT_GO (opencode)."
        )


REGISTRY: list[Pattern] = [
    LockedPrefixAndLateInjection(),
    ToolOutputDegradation(),
    CompactionWithPrefixRebuild(),
    IsolatedSubagents(),
    FileStalenessDetection(),
    HardwareAwareConfig(),
]

BY_ID = {p.id: p for p in REGISTRY}