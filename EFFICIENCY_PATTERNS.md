# Cortex-Agent Efficiency Patterns

This document captures the core efficiency mechanisms from cortex-agent that can be ported into any AI coding client (opencode, hermes, claude-code, aider, etc.).

Cortex-agent is no longer just a standalone agent — it's a **reference implementation of context-window efficiency patterns** that other clients can adopt. The bundled smart installer (`smart_installer/`) can probe a client's source tree, show porting guidance, and apply a verified recipe automatically.

---

## The Core Problem

All AI coding agents face the same constraint: **context windows are finite and prompt caching only works on byte-identical prefixes**.

Naive agents:
- Accumulate full tool outputs forever → context fills fast
- Bake env info (time, git, cwd) into system prompt → changes every turn = cache miss
- Let subagents inherit parent context → exploration burns main transcript tokens
- Never revisit old tool results → waste budget on stale data

---

## Pattern 1: Locked Prefix + Late Injection

**What:** Split message list into `[locked prefix]` + `[mutable tail]`. Never mutate locked prefix. Inject per-turn context (time, git branch, file changes, todos) as an ephemeral tail message at send time — never stored.

**Why:** LLM providers (OpenAI, Anthropic, DeepSeek) cache the prefix. Mutating it = full re-encode = higher latency + cost.

**Implementation:**
```python
# Find locked boundary (after last summary marker)
def locked(messages):
    for i in reversed(range(len(messages))):
        if "Summary:" in messages[i].get("content", ""):
            return i + 1
    return 1  # system prompt only

# At send time: create fresh injection, append to copy
injection = build_env_injection()  # time, git, cwd, todos
msgs_to_send = messages + [injection]  # never mutates `messages`
response = llm.call(msgs_to_send)
```

**Porting notes:**
- Add `locked_prefix_len` tracking to session/message store
- Modify system prompt: remove dynamic env info
- Add injection builder (git branch cache it per-process)
- Ensure injection is appended at call site, not in history

---

## Pattern 2: Three-Tier Tool Output Degradation

**What:** Progressively shrink tool outputs over their lifetime.

| Phase | When | Action | Budget |
|-------|------|--------|--------|
| **Cap** | At creation | Truncate inline to 10K chars; spill full to temp file | ~3.3K tokens |
| **Strip** | End of turn | Reduce to 300-char stub + "[output trimmed: N more chars]" | ~100 tokens |
| **Drop** | Emergency | Discard oldest tool results entirely until under budget | 0 tokens |

**Why:** A single `grep` can emit 50K chars. Without degradation, 3 tool calls = context full.

**Implementation:**
```python
CAP = 10_000
STUB = 300

def cap(output):
    if len(output) <= CAP: return output
    path = spill_to_disk(output)
    return output[:CAP] + f"\n\n[trimmed {len(output)-CAP} chars; full at {path}]"

def strip(messages, locked_len):
    for msg in messages[locked_len:]:
        if msg.role == "tool" and not already_stripped(msg):
            msg.content = msg.content[:STUB] + f"\n\n[output trimmed: {len(msg.content)-STUB} more chars]"

def drop(messages, locked_len, budget):
    for msg in messages[locked_len:]:  # oldest first
        if msg.role == "tool" and estimate_tokens(messages) > budget:
            msg.content = "[dropped to fit context window]"
```

**Porting notes:**
- Add `cap()` in tool execution layer (bash, view, grep, etc.)
- Add `strip()` call at turn boundary in agent loop
- Add `drop()` as pre-flight check before LLM call
- Mark stripped results with a sentinel (`[output trimmed:`) for idempotency

---

## Pattern 3: Compaction with Prefix Rebuild

**What:** When prompt tokens > 85% of window, summarize old messages into a single handoff note. Rebuild message list as: `system + summary + recent_tail (35%)`. The new `system + summary` becomes the new locked prefix.

**Why:** Keeps recent context intact while freeing 50% of window. Single LLM call for summarization is cheaper than re-encoding full history every turn.

**Implementation:**
```python
COMPACT_AT = 0.85
COMPACT_TO = 0.35

def compact(messages):
    # Find cut point: keep most recent 35% of tokens
    cut = find_tail_boundary(messages, budget=CONTEXT_WINDOW * COMPACT_TO)
    # Summarize everything before cut
    summary = llm.summarize(messages[1:cut])  # skip system
    # Rebuild: system + summary + tail
    new_messages = [
        messages[0],  # system (byte-identical)
        {"role": "user", "content": f"Summary: {summary}"},
        *messages[cut:]
    ]
    strip(new_messages)  # safe: prefix being rebuilt anyway
    return new_messages
```

**Porting notes:**
- Needs separate summarization model/provider (cheaper/faster)
- Summary must contain "Summary:" marker for locked prefix detection
- Trigger on `usage.prompt_tokens > CONTEXT_WINDOW * 0.85`
- After compaction, locked prefix = `[system, summary]`

---

## Pattern 4: Isolated Subagents (Task Tool)

**What:** Exploration subagents run in a **completely fresh context window** with:
- Empty message history (system + user prompt only)
- Restricted toolset: read-only (no bash, write, edit, task, todos)
- Hard turn limit (12)
- Only final answer returns to caller

**Why:** "Exploring a repo burns tens of thousands of tokens of tool output to produce a few hundred tokens of answer." Subagent spends tokens in a throwaway window; main agent pays only for the distilled answer.

**Implementation:**
```python
def run_subagent(prompt, max_turns=12):
    messages = [
        {"role": "system", "content": SUBAGENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    tools = READ_ONLY_TOOLS  # no write, no task, no todos
    
    for turn in range(max_turns):
        response = llm.call(messages, tools)
        if not response.tool_calls:
            return response.content  # only this crosses back
        messages.append(response)
        for tc in response.tool_calls:
            result = execute(tc)
            messages.append(result)
    return "Max turns reached"
```

**Porting notes:**
- Create separate agent instance with empty history
- Tool registry: filter out mutating tools
- Pass only final text response to parent
- Cost accounting: attribute subagent tokens to parent session

---

## Pattern 5: File Staleness Detection

**What:** Track `os.stat(mtime, size)` per file per turn. Warn agent when a file it read has changed since last read.

**Why:** Prevents agent from editing stale versions, reduces re-reads, catches external changes (git pull, other editors).

**Implementation:**
```python
LAST_STATS = {}

def check_stale(files_read_this_turn):
    warnings = []
    for path in files_read_this_turn:
        stat = os.stat(path)
        key = (stat.st_mtime, stat.st_size)
        if LAST_STATS.get(path) != key:
            warnings.append(f"modified: {path}")
        LAST_STATS[path] = key
    return warnings
```

**Porting notes:**
- Hook into file read tool (view, read)
- Inject warnings via late injection or tool result metadata
- Cheap: `os.stat` is O(1), no hashing

---

## Pattern 6: Hardware-Aware Automatic Configuration

**What:** Detect system hardware (GPU vendor/model/VRAM, CPU, RAM, OS) at startup and automatically configure optimal defaults for context window, quantization, GPU memory utilization, CPU offload, and subagent limits.

**Why:** Optimal settings vary dramatically by hardware. A 16GB GPU needs different context/quantization than a 48GB GPU or Apple Silicon unified memory.

**Implementation:**
```python
def detect_hardware():
    # Returns: GPU vendor/model/VRAM/unified, CPU cores/model, RAM bytes, OS
    hw = HardwareInfo(
        gpu=GPUInfo(vendor="nvidia", model="RTX 5060 Ti", vram_bytes=17_103_323_136, unified_memory=False),
        cpu=CPUInfo(model="AMD Ryzen 9 7900X", cores=16, threads=16),
        ram_bytes=34_359_738_368,
        os="Windows", os_version="11", arch="AMD64"
    )
    return hw

def get_profile(hw):
    # Maps hardware to profile with optimal settings
    if hw.gpu.vendor == "nvidia" and hw.gpu.vram_bytes >= 24 * GiB:
        return Profile(context_window=128000, quantization="FP16", gpu_mem=0.9, cpu_offload_gb=64)
    elif hw.gpu.vendor == "nvidia" and hw.gpu.vram_bytes >= 8 * GiB:
        return Profile(context_window=65536, quantization="FP16", gpu_mem=0.85, cpu_offload_gb=32)
    # ... more profiles
```

**Porting notes:**
- Detect GPU via `nvidia-smi`, `rocm-smi`, `lspci`, `wmic`, `system_profiler`
- Detect RAM via `/proc/meminfo`, `sysctl`, `wmic`
- Map to 5 profiles: high_end, mid_range, low_end, apple_silicon, cpu_only
- Apply defaults at config load; allow user override in config file

---

## Patcher Reference: Smart Installer

`smart_installer/` is a **source-code patcher** that implements these
patterns into any AI coding client. It is not an LLM-stack installer — it
patches client source code, using the six patterns above as its library.

- **Probe** (`python -m smart_installer <client-tree>`) — assesses each pattern
  and reports `applied / partial / absent` with the hook points found.
- **Guide** (`--guide`) — prints per-pattern porting instructions tuned to the
  detected language.
- **Recipe apply** (`--apply --dry-run` / `--apply`) — applies a verified,
  idempotent edit-plan for a known client (opencode is shipped), with
  git-checkout safety, timestamped backups, and per-edit marker checks.

Structure:

- `core/target.py` — client detection + source-tree index
- `detect/` — client / language detection
- `patterns/library.py` — the six probes (the plugin API)
- `recipes/` — per-client `EditPlan`s; opencode is the shipped reference
- `engine.py` — dry-run, backup, idempotent apply, diff preview
- `__main__.py` — CLI

Adding a new client = one recipe function in `recipes/__init__.py`
(see `smart_installer/README.md`).

---

## Porting Checklist for Target Client

| Pattern | Files to Modify | Difficulty |
|---------|----------------|------------|
| Locked prefix + late injection | agent loop, system prompt builder, message store | Medium |
| Cap/Strip/Drop | tool executors, agent loop, message store | Medium |
| Compaction | agent loop, summarization provider, session store | High |
| Subagent isolation | agent factory, tool registry, task tool | Medium |
| File staleness | file read tool, injection builder | Low |
| Hardware-aware config | config loader, hardware detection, defaults | Medium |

---

## Reference Implementation: Opencode Patch

The opencode recipe in `smart_installer/recipes/` is encoded from a tested Go
patch and reproduces all six patterns against a real client:

- `internal/message/message.go`: StripToolResults, locked prefix finder
- `internal/llm/agent/agent.go`: late injection, turn-loop compaction trigger, maxTurns
- `internal/llm/prompt/coder.go`: removed env info from system prompt
- `internal/llm/prompt/task.go`: rewritten for strict isolation
- `internal/llm/tools/bash.go`: MaxOutputLength 30K→10K
- `internal/llm/tools/view.go`: MaxReadSize 250KB→100KB, DefaultReadLimit 2000→500
- `internal/hardware/detect.go`: **New** — cross-platform GPU/CPU/RAM detection, 5 hardware profiles
- `internal/config/config.go`: **New** — hardware-aware defaults via `applyHardwareDefaults()`
- `internal/filetrack/tracker.go`: **New** — file staleness detection via `os.stat(mtime, size)`
- `internal/filetrack/global.go`: **New** — global tracker for file read recording

---

## Usage as a Patcher

To use cortex-agent as a patcher for another client:

1. **Clone target client source**
2. **Apply patterns** using this doc as reference
3. **Test** with long sessions (30+ turns) and large tool outputs
4. **Verify** prompt cache hits via provider usage metrics (`cache_read_tokens > 0`)

The patterns are language-agnostic — they work in Go, Python, TypeScript, Rust — wherever the agent loop lives.