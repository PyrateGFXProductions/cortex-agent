"""Pressure response: auto-adjust strategy based on context load."""

from .. import config as cfg
from .. import history

from .base import IntelligenceModule, ModulePhase


class PressureResponse(IntelligenceModule):
    """Dynamically shift strategy as context fills.
    
    Phases:
    - LOW (0-70%): normal, use any tool
    - MEDIUM (70-85%): efficiency, prefer read_file over bash
    - HIGH (85-95%): conservation, batch edits, no subagents
    - CRITICAL (>95%): auto-compact if enabled
    """
    
    name = "pressure_response"
    description = "Auto-adjust strategy based on context pressure"
    enabled_by_default = True
    phase = ModulePhase.CONTEXT_CHECK
    
    def can_run(self) -> bool:
        """Always check context pressure."""
        return self.config.get("pressure_response", {}).get("enabled", True)
    
    def execute(self, messages=None, **kwargs):
        """Assess pressure and inject strategy guidance.
        
        Args:
            messages: Current message history
        
        Returns:
            Dict message to inject, or None
        """
        if not messages:
            return None
        
        used = history.estimate(messages)
        pct = used / cfg.CONTEXT_WINDOW
        
        strategy = self._get_strategy(pct)
        
        if strategy["level"] == "LOW":
            return None  # No message needed
        
        # Inject strategy guidance
        return {
            "role": "user",
            "content": strategy["instruction"],
        }
    
    def _get_strategy(self, pct: float) -> dict:
        """Determine strategy based on pressure percentage."""
        if pct < 0.70:
            return {
                "level": "LOW",
                "instruction": None,
            }
        
        if pct < 0.85:
            return {
                "level": "MEDIUM",
                "instruction": """EFFICIENCY MODE: Context usage at {:.0f}%.
Prefer:
• read_file for specific files (deterministic)
• str_replace for edits (small output)
Skip optional exploration.""".format(pct * 100),
            }
        
        if pct < 0.95:
            return {
                "level": "HIGH",
                "instruction": """⚠️ HIGH PRESSURE: Context usage at {:.0f}%.
Switch to conservation mode:
• NO task subagents (waste new context)
• Batch all edits into one str_replace
• Use read_skill for complex tasks
• Keep tool results short (head/tail/grep)""".format(pct * 100),
            }
        
        return {
            "level": "CRITICAL",
            "instruction": """🚨 CRITICAL OVERFLOW: Context at {:.0f}%.
Immediate action needed:
• Stop exploring
• Finish current task quickly
• Type /compact to summarize and reset""".format(pct * 100),
        }
