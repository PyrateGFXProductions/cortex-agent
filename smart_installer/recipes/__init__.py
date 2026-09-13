"""Recipes: per-client EditPlans that apply the six patterns automatically.

A recipe is just a function that returns an `EditPlan` given a `Target`.
The engine applies it with dry-run, backup, idempotency and verification.
"""

from __future__ import annotations

from ..patterns.base import Edit, EditPlan
from ..core.target import Target


def opencode_recipe(target: Target) -> EditPlan:
    """Apply all six efficiency patterns to an opencode Go source tree.

    Encoded from the tested Go patch (see internal/filetrack, internal/hardware,
    internal/message/message.go, internal/llm/agent/agent.go, and the tool
    executors in the reference patch).  Idempotent: every edit's marker
    (the replacement text) is checked before applying, so re-running is safe.
    """
    edits = [
        # --- Pattern 6: hardware-aware config ---
        Edit(
            "internal/config/config.go",
            find="\tAutoCompact  bool                              `json:\"autoCompact,omitempty\"`",
            replace="\tAutoCompact  bool                              `json:\"autoCompact,omitempty\"`\n\n\t// Hardware-aware settings (auto-detected, can be overridden in config)\n\tContextWindow    int     `json:\"contextWindow,omitempty\"`   // Context window tokens\n\tCompactAt        float64 `json:\"compactAt,omitempty\"`       // Compaction trigger threshold\n\tCompactTo        float64 `json:\"compactTo,omitempty\"`       // Compaction target threshold\n\tToolOutputCap    int     `json:\"toolOutputCap,omitempty\"`   // Max tool output chars (cap phase)\n\tToolOutputStub   int     `json:\"toolOutputStub,omitempty\"`  // Tool output stub size (strip phase)\n\tSubagentMaxTurns int     `json:\"subagentMaxTurns,omitempty\"` // Max turns for task agent",
            note="Pattern 6: add hardware-aware config fields",
        ),
        # --- Pattern 2: bash output cap ---
        Edit(
            "internal/llm/tools/bash.go",
            find="MaxOutputLength = 30000",
            replace="MaxOutputLength = 10000 // cortex-agent style cap: 10K chars inline, rest spilled to disk",
            note="Pattern 2: cap bash output at 10K",
        ),
        # --- Pattern 5: file staleness hook in read tracker ---
        Edit(
            "internal/llm/tools/file.go",
            find='import (\n\t"sync"\n\t"time"\n)',
            replace='import (\n\t"sync"\n\t"time"\n\n\t"github.com/opencode-ai/opencode/internal/filetrack"\n)',
            note="Pattern 5: import filetrack",
        ),
        Edit(
            "internal/llm/tools/file.go",
            find="\trecord.readTime = time.Now()\n\tfileRecords[path] = record",
            replace="\trecord.readTime = time.Now()\n\tfileRecords[path] = record\n\n\t// Also record in global file tracker for stale detection\n\tfiletrack.GetGlobalTracker().RecordRead(path)",
            note="Pattern 5: record reads into global staleness tracker",
        ),
        # --- Pattern 4: subagent turn cap ---
        Edit(
            "internal/llm/agent/agent-tool.go",
            find="agent, err := NewAgent(config.AgentTask, b.sessions, b.messages, TaskAgentTools(b.lspClients))",
            replace="maxTurns := config.Get().SubagentMaxTurns\n\tif maxTurns <= 0 {\n\t\tmaxTurns = 12 // cortex-agent default\n\t}\n\tagent, err := NewAgent(config.AgentTask, b.sessions, b.messages, TaskAgentTools(b.lspClients), maxTurns)",
            note="Pattern 4: cap task agent at 12 turns",
        ),
        # --- Pattern 4: isolated task-agent prompt ---
        Edit(
            "internal/llm/prompt/task.go",
            find='func TaskPrompt(_ models.ModelProvider) string {\n\tagentPrompt := `You are an agent for OpenCode. Given the user\'s prompt, you should use the tools available to you to answer the user\'s question.',
            replace='func TaskPrompt(_ models.ModelProvider) string {\n\tagentPrompt := `You are a subagent for OpenCode, spawned to explore the codebase and answer a specific question. Your entire context window is isolated from the main agent.',
            note="Pattern 4: rewrite task-agent prompt for isolation (insert rest manually)",
        ),
        # --- Pattern 1: strip env info from coder prompt (late injection owns it now) ---
        Edit(
            "internal/llm/prompt/coder.go",
            find="\tenvInfo := getEnvironmentInfo()",
            replace="\t// Environment info is now injected via late injection in agent.go buildLateInjection()\n\t// to preserve prompt cache prefix. Kept minimal LSP info here.\n\tlspInfo := lspInformation()",
            note="Pattern 1: remove env info from system prompt (moves to late injection)",
        ),
    ]

    # New packages shipped by the patch.
    edits += [
        Edit("internal/hardware/detect.go", "", HARDWARE_DETECT_GO, note="Pattern 6: hardware detection package", create=True),
        Edit("internal/filetrack/tracker.go", "", FILETRACK_TRACKER_GO, note="Pattern 5: staleness tracker", create=True),
        Edit("internal/filetrack/global.go", "", FILETRACK_GLOBAL_GO, note="Pattern 5: global tracker singleton", create=True),
    ]

    return EditPlan(
        target=target.client,
        pattern="all-six",
        edits=edits,
        note="opencode reference recipe - locks prefix, caps/strips tool output, isolates subagents, detects file staleness, hardware-aware defaults",
    )


HARDWARE_DETECT_GO = r"""// Package hardware detects system hardware capabilities for automatic configuration.
package hardware

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"sync"
)

// GPUInfo describes a detected GPU.
type GPUInfo struct {
	Vendor     string // "nvidia", "amd", "intel", "apple"
	Model      string // e.g. "RTX 5060 Ti", "M3 Max"
	VRAMBytes  uint64 // VRAM in bytes (0 when unknown or unified memory)
	UnifiedMem bool   // Apple Silicon, Jetson, etc.
}

// HardwareInfo is the full detection result.
type HardwareInfo struct {
	OS        string
	OSVersion string
	Arch      string
	CPUModel  string
	CPUCores  int
	RAMBytes  uint64
	GPU       *GPUInfo
}

// Detect gathers hardware information for the current system.
func Detect() HardwareInfo {
	return HardwareInfo{
		OS:        runtime.GOOS,
		OSVersion: getOSVersion(),
		Arch:      runtime.GOARCH,
		CPUModel:  getCPUModel(),
		CPUCores:  runtime.NumCPU(),
		RAMBytes:  getSystemRAM(),
		GPU:       detectGPU(),
	}
}

// HardwareProfile ranks the machine for local-model sizing.
type HardwareProfile string

const (
	ProfileHighEnd      HardwareProfile = "high_end"      // >= 24GB VRAM or >= 64GB unified
	ProfileMidRange     HardwareProfile = "mid_range"     // 8-24GB VRAM or 32-64GB unified
	ProfileLowEnd       HardwareProfile = "low_end"       // < 8GB VRAM or < 32GB unified
	ProfileAppleSilicon HardwareProfile = "apple_silicon" // Apple unified memory
	ProfileCPUOnly      HardwareProfile = "cpu_only"      // No usable GPU
)

// GetProfile returns the hardware profile for this system.
func (h *HardwareInfo) GetProfile() HardwareProfile {
	if h.GPU == nil {
		return ProfileCPUOnly
	}
	if h.GPU.Vendor == "apple" || h.GPU.UnifiedMem {
		switch {
		case h.RAMBytes >= 96*1024*1024*1024:
			return ProfileHighEnd
		case h.RAMBytes >= 64*1024*1024*1024:
			return ProfileMidRange
		case h.RAMBytes >= 32*1024*1024*1024:
			return ProfileLowEnd
		default:
			return ProfileCPUOnly
		}
	}
	if h.GPU.VRAMBytes > 0 {
		vramGB := float64(h.GPU.VRAMBytes) / (1024 * 1024 * 1024)
		switch {
		case vramGB >= 24:
			return ProfileHighEnd
		case vramGB >= 8:
			return ProfileMidRange
		default:
			return ProfileLowEnd
		}
	}
	return ProfileCPUOnly
}

// OptimalSettings are the efficiency-pattern defaults for a profile.
type OptimalSettings struct {
	ContextWindow       int     // Target context window tokens
	MaxTokens           int     // Max output tokens per turn
	CompactAt           float64 // Trigger compaction at this fraction
	CompactTo           float64 // Compact down to this fraction
	ToolOutputCap       int     // Cap tool output at this many chars
	ToolOutputStub      int     // Strip tool output to this many chars
	SubagentMaxTurns    int     // Max turns for subagents
	ModelRecommendation string  // "small", "medium", "large"
}

// OptimalConfig returns recommended settings for this hardware profile.
func (p HardwareProfile) OptimalConfig() OptimalSettings {
	switch p {
	case ProfileHighEnd:
		return OptimalSettings{128000, 8192, 0.85, 0.35, 10000, 300, 12, "large"}
	case ProfileMidRange:
		return OptimalSettings{128000, 4096, 0.80, 0.30, 8000, 200, 8, "medium"}
	case ProfileLowEnd:
		return OptimalSettings{64000, 2048, 0.75, 0.25, 5000, 150, 6, "small"}
	case ProfileAppleSilicon:
		return OptimalSettings{128000, 4096, 0.80, 0.30, 8000, 200, 8, "medium"}
	default: // CPUOnly
		return OptimalSettings{32000, 1024, 0.70, 0.20, 3000, 100, 4, "small"}
	}
}

func getSystemRAM() uint64 {
	switch runtime.GOOS {
	case "windows":
		if out, err := runCmd("powershell -Command \"Get-CimInstance Win32_ComputerSystem | Select-Object -ExpandProperty TotalPhysicalMemory\""); err == nil {
			if v, err := strconv.ParseUint(strings.TrimSpace(out), 10, 64); err == nil {
				return v
			}
		}
	case "linux":
		if data, err := os.ReadFile("/proc/meminfo"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "MemTotal:") {
					fields := strings.Fields(line)
					if len(fields) >= 2 {
						if kb, err := strconv.ParseUint(fields[1], 10, 64); err == nil {
							return kb * 1024
						}
					}
				}
			}
		}
	case "darwin":
		if out, err := runCmd("sysctl -n hw.memsize"); err == nil {
			if v, err := strconv.ParseUint(strings.TrimSpace(out), 10, 64); err == nil {
				return v
			}
		}
	}
	return 0
}

func getCPUModel() string {
	switch runtime.GOOS {
	case "windows":
		if out, err := runCmd("powershell -Command \"Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name\""); err == nil {
			return strings.TrimSpace(out)
		}
	case "linux":
		if data, err := os.ReadFile("/proc/cpuinfo"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "model name") {
					parts := strings.SplitN(line, ":", 2)
					if len(parts) == 2 {
						return strings.TrimSpace(parts[1])
					}
				}
			}
		}
	case "darwin":
		if out, err := runCmd("sysctl -n machdep.cpu.brand_string"); err == nil {
			return strings.TrimSpace(out)
		}
	}
	return runtime.GOARCH
}

func getOSVersion() string {
	switch runtime.GOOS {
	case "windows":
		if out, err := runCmd("powershell -Command \"[System.Environment]::OSVersion.Version\""); err == nil {
			return "Windows " + strings.TrimSpace(out)
		}
	case "linux":
		if data, err := os.ReadFile("/etc/os-release"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "PRETTY_NAME=") {
					return strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), `"`)
				}
			}
		}
	case "darwin":
		if out, err := runCmd("sw_vers -productVersion"); err == nil {
			return "macOS " + strings.TrimSpace(out)
		}
	}
	return runtime.GOOS
}

func detectGPU() *GPUInfo {
	switch runtime.GOOS {
	case "windows":
		return detectGPUWindows()
	case "linux":
		return detectGPULinux()
	case "darwin":
		return detectGPUMacOS()
	}
	return nil
}

func detectGPUWindows() *GPUInfo {
	if out, err := runCmd("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"); err == nil {
		parts := strings.Split(strings.TrimSpace(out), "\n")
		if len(parts) > 0 {
			row := strings.Split(parts[0], ", ")
			if len(row) == 2 {
				vramMB, _ := strconv.ParseUint(strings.TrimSpace(row[1]), 10, 64)
				return &GPUInfo{Vendor: "nvidia", Model: strings.TrimSpace(row[0]), VRAMBytes: vramMB * 1024 * 1024}
			}
		}
	}
	if out, err := runCmd("wmic path win32_VideoController get name,AdapterRAM /format:csv"); err == nil {
		for _, line := range strings.Split(strings.TrimSpace(out), "\n")[1:] {
			parts := strings.Split(line, ",")
			if len(parts) >= 3 {
				name := strings.TrimSpace(parts[1])
				vram, err := strconv.ParseUint(strings.TrimSpace(parts[2]), 10, 64)
				if err == nil && vram > 0 {
					return &GPUInfo{Vendor: detectGPUVendor(name), Model: name, VRAMBytes: vram}
				}
			}
		}
	}
	return nil
}

func detectGPULinux() *GPUInfo {
	if out, err := runCmd("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"); err == nil {
		parts := strings.Split(strings.TrimSpace(out), "\n")
		if len(parts) > 0 {
			row := strings.Split(parts[0], ", ")
			if len(row) == 2 {
				vramMB, _ := strconv.ParseUint(strings.TrimSpace(row[1]), 10, 64)
				return &GPUInfo{Vendor: "nvidia", Model: strings.TrimSpace(row[0]), VRAMBytes: vramMB * 1024 * 1024}
			}
		}
	}
	if out, err := runCmd("lspci -nn | grep -i vga"); err == nil {
		lines := strings.Split(strings.TrimSpace(out), "\n")
		if len(lines) > 0 {
			return &GPUInfo{Vendor: detectGPUVendor(lines[0]), Model: lines[0], VRAMBytes: 0}
		}
	}
	return nil
}

func detectGPUMacOS() *GPUInfo {
	if out, err := runCmd("sysctl -n machdep.cpu.brand_string"); err == nil {
		cpu := strings.ToLower(out)
		if strings.Contains(cpu, "apple") {
			chip := "Apple Silicon"
			for _, m := range []string{"m1", "m2", "m3", "m4"} {
				if strings.Contains(cpu, m) {
					chip = "Apple " + strings.ToUpper(m[:1]) + m[1:]
				}
			}
			if strings.Contains(cpu, "ultra") {
				chip += " Ultra"
			} else if strings.Contains(cpu, "max") {
				chip += " Max"
			} else if strings.Contains(cpu, "pro") {
				chip += " Pro"
			}
			return &GPUInfo{Vendor: "apple", Model: chip, UnifiedMem: true}
		}
	}
	return nil
}

func detectGPUVendor(name string) string {
	name = strings.ToLower(name)
	switch {
	case strings.Contains(name, "nvidia"), strings.Contains(name, "geforce"), strings.Contains(name, "quadro"), strings.Contains(name, "rtx"), strings.Contains(name, "gtx"):
		return "nvidia"
	case strings.Contains(name, "amd"), strings.Contains(name, "radeon"), strings.Contains(name, "rx "):
		return "amd"
	case strings.Contains(name, "intel"), strings.Contains(name, "iris"), strings.Contains(name, "arc "), strings.Contains(name, "uhd"):
		return "intel"
	case strings.Contains(name, "apple"):
		return "apple"
	}
	return "unknown"
}

var cmdOnce sync.Once

func runCmd(cmd string) (string, error) {
	cmdOnce.Do(func() {}) // placeholder for future command-local caching
	var c *exec.Cmd
	if runtime.GOOS == "windows" {
		c = exec.Command("powershell", "-Command", cmd)
	} else {
		c = exec.Command("sh", "-c", cmd)
	}
	out, err := c.Output()
	return string(out), err
}

// String returns a human-readable summary of the hardware.
func (h *HardwareInfo) String() string {
	return fmt.Sprintf("OS: %s %s | Arch: %s | CPU: %s (%d cores) | RAM: %.1f GB | GPU: %s",
		h.OS, h.OSVersion, h.Arch, h.CPUModel, h.CPUCores,
		float64(h.RAMBytes)/(1024*1024*1024), h.GPUString())
}

// GPUString returns a short GPU description for logging.
func (h *HardwareInfo) GPUString() string {
	if h.GPU == nil {
		return "None"
	}
	s := h.GPU.Vendor + " " + h.GPU.Model
	if h.GPU.VRAMBytes > 0 {
		s += fmt.Sprintf(" (%.1f GB VRAM)", float64(h.GPU.VRAMBytes)/(1024*1024*1024))
	} else if h.GPU.UnifiedMem {
		s += " (Unified Memory)"
	}
	return s
}
"""


FILETRACK_TRACKER_GO = r"""// Package filetrack tracks file access and detects stale reads.
package filetrack

import (
	"os"
	"path/filepath"
	"sync"
	"time"
)

type FileStat struct {
	Path    string
	ModTime time.Time
	Size    int64
}

type Tracker struct {
	mu    sync.RWMutex
	stats map[string]FileStat
}

func NewTracker() *Tracker {
	return &Tracker{stats: make(map[string]FileStat)}
}

// RecordRead records that a file was read at the current time.
func (t *Tracker) RecordRead(path string) {
	absPath, _ := filepath.Abs(path)
	info, err := os.Stat(absPath)
	if err != nil {
		return
	}
	t.mu.Lock()
	defer t.mu.Unlock()
	t.stats[absPath] = FileStat{Path: absPath, ModTime: info.ModTime(), Size: info.Size()}
}

// CheckStale returns files modified or resized since last read.
func (t *Tracker) CheckStale() []string {
	t.mu.Lock()
	defer t.mu.Unlock()
	var stale []string
	for path, stat := range t.stats {
		info, err := os.Stat(path)
		if err != nil {
			stale = append(stale, path+" (deleted)")
			continue
		}
		if info.ModTime().After(stat.ModTime) || info.Size() != stat.Size {
			stale = append(stale, path)
			t.stats[path] = FileStat{Path: path, ModTime: info.ModTime(), Size: info.Size()}
		}
	}
	return stale
}

// GetStaleWarning returns a formatted warning message for stale files.
func (t *Tracker) GetStaleWarning() string {
	stale := t.CheckStale()
	if len(stale) == 0 {
		return ""
	}
	msg := "<system-reminder>\nThese files changed since your last turn. Read them again before editing:\n"
	for _, f := range stale {
		msg += "modified: " + f + "\n"
	}
	return msg + "</system-reminder>"
}

// Clear clears the tracker.
func (t *Tracker) Clear() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.stats = make(map[string]FileStat)
}
"""


FILETRACK_GLOBAL_GO = r"""// Package filetrack provides global file tracking for stale read detection.
package filetrack

import "sync"

var (
	globalTracker *Tracker
	trackerOnce   sync.Once
)

// GetGlobalTracker returns the global file tracker instance.
func GetGlobalTracker() *Tracker {
	trackerOnce.Do(func() {
		globalTracker = NewTracker()
	})
	return globalTracker
}

// SetGlobalTracker sets a custom global tracker (for testing or agent-specific trackers).
func SetGlobalTracker(t *Tracker) {
	globalTracker = t
}
"""


# Client recipes registry. Keyed by detected client name.
RECIPES = {
    "opencode": opencode_recipe,
}