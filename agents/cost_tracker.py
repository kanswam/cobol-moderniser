"""
=============================================================================
COST TRACKER MODULE
=============================================================================
Purpose:
    Track API costs across the COBOL Moderniser pipeline.

    Only Agent 2 (Logic Extractor) makes API calls, so this module is
    currently used by that agent.  It is designed to be generic enough
    that additional agents can be added later without changing the API.

    The module uses **only** the Python standard library so it adds no
    external dependencies.

Usage:
    from agents.cost_tracker import CostTracker, PRICING

    tracker = CostTracker()
    tracker.record(
        agent="Logic Extractor",
        model="claude-sonnet-4-20250514",
        input_tokens=1500,
        output_tokens=400,
        duration_seconds=2.5,
    )
    tracker.print_summary()
    tracker.save("output/cost_report.json")
=============================================================================
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# PRICING TABLE
# ---------------------------------------------------------------------------
# Per-model pricing in USD per 1 000 000 tokens.
# Add new models here; no other code needs to change.
# ---------------------------------------------------------------------------

PRICING: Dict[str, Dict[str, float]] = {
    "claude-sonnet-4-20250514": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    "claude-opus-4-6": {
        "input_per_million": 15.00,
        "output_per_million": 75.00,
    },
    "claude-haiku-4-5-20251001": {
        "input_per_million": 0.80,
        "output_per_million": 4.00,
    },
}

# Default/fallback prices when a model is not found in PRICING.
_DEFAULT_INPUT_PPM = 3.00
_DEFAULT_OUTPUT_PPM = 15.00


# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class APICall:
    """A single recorded API call."""

    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def total_tokens(self) -> int:
        """Return the combined token count."""
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        """Calculate cost in USD for this call."""
        pricing = PRICING.get(self.model, {})
        input_ppm = pricing.get("input_per_million", _DEFAULT_INPUT_PPM)
        output_ppm = pricing.get("output_per_million", _DEFAULT_OUTPUT_PPM)
        return (
            self.input_tokens / 1_000_000 * input_ppm
            + self.output_tokens / 1_000_000 * output_ppm
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict for JSON output."""
        return {
            "agent": self.agent,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "duration_seconds": round(self.duration_seconds, 4),
            "cost_usd": round(self.cost_usd, 8),
            "timestamp": self.timestamp,
        }


@dataclass
class ModelStats:
    """Aggregated statistics for a single model."""

    model: str
    call_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
    total_cost_usd: float = 0.0

    def add(self, call: APICall) -> None:
        """Incorporate a single API call into the aggregates."""
        self.call_count += 1
        self.total_input_tokens += call.input_tokens
        self.total_output_tokens += call.output_tokens
        self.total_tokens += call.total_tokens
        self.total_duration_seconds += call.duration_seconds
        self.total_cost_usd += call.cost_usd

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict for JSON output."""
        return {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_duration_seconds": round(self.total_duration_seconds, 4),
            "total_cost_usd": round(self.total_cost_usd, 8),
        }


# ---------------------------------------------------------------------------
# COST TRACKER
# ---------------------------------------------------------------------------

class CostTracker:
    """
    Record and aggregate API call costs across the pipeline.

    Thread-safety:
        This class is **not** thread-safe.  If multiple agents run
        concurrently, protect the instance with a lock.
    """

    def __init__(self) -> None:
        self._calls: List[APICall] = []
        self._started_at: str = datetime.now(timezone.utc).isoformat()

    # -- Recording --------------------------------------------------------

    def record(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
    ) -> None:
        """
        Record a single API call.

        Parameters
        ----------
        agent:
            Human-readable name of the agent that made the call,
            e.g. ``"Logic Extractor"``.
        model:
            Model identifier used for the call,
            e.g. ``"claude-sonnet-4-20250514"``.
        input_tokens:
            Number of tokens sent in the request.
        output_tokens:
            Number of tokens received in the response.
        duration_seconds:
            Wall-clock time for the HTTP request/response round-trip.
        """
        call = APICall(
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=duration_seconds,
        )
        self._calls.append(call)

    # -- Queries ----------------------------------------------------------

    @property
    def total_cost_usd(self) -> float:
        """Sum of costs for all recorded calls (USD)."""
        return sum(call.cost_usd for call in self._calls)

    @property
    def total_tokens(self) -> int:
        """Sum of *all* tokens (input + output) across all calls."""
        return sum(call.total_tokens for call in self._calls)

    @property
    def total_input_tokens(self) -> int:
        """Sum of input tokens across all calls."""
        return sum(call.input_tokens for call in self._calls)

    @property
    def total_output_tokens(self) -> int:
        """Sum of output tokens across all calls."""
        return sum(call.output_tokens for call in self._calls)

    @property
    def total_duration_seconds(self) -> float:
        """Sum of durations across all calls."""
        return sum(call.duration_seconds for call in self._calls)

    @property
    def call_count(self) -> int:
        """Number of recorded API calls."""
        return len(self._calls)

    @property
    def has_records(self) -> bool:
        """``True`` if at least one call has been recorded."""
        return len(self._calls) > 0

    def by_model(self) -> Dict[str, ModelStats]:
        """
        Aggregate statistics grouped by model.

        Returns
        -------
        dict
            Mapping of model name -> ``ModelStats``.
        """
        stats: Dict[str, ModelStats] = {}
        for call in self._calls:
            if call.model not in stats:
                stats[call.model] = ModelStats(model=call.model)
            stats[call.model].add(call)
        return stats

    def by_agent(self) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate statistics grouped by agent.

        Returns
        -------
        dict
            Mapping of agent name -> aggregated stats dict.
        """
        agents: Dict[str, Dict[str, Any]] = {}
        for call in self._calls:
            name = call.agent
            if name not in agents:
                agents[name] = {
                    "agent": name,
                    "call_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "total_duration_seconds": 0.0,
                    "total_cost_usd": 0.0,
                    "models_used": set(),
                }
            agents[name]["call_count"] += 1
            agents[name]["total_input_tokens"] += call.input_tokens
            agents[name]["total_output_tokens"] += call.output_tokens
            agents[name]["total_tokens"] += call.total_tokens
            agents[name]["total_duration_seconds"] += call.duration_seconds
            agents[name]["total_cost_usd"] += call.cost_usd
            agents[name]["models_used"].add(call.model)

        # Convert sets to lists for JSON serialisation.
        for entry in agents.values():
            entry["models_used"] = sorted(entry["models_used"])
            entry["total_duration_seconds"] = round(entry["total_duration_seconds"], 4)
            entry["total_cost_usd"] = round(entry["total_cost_usd"], 8)

        return agents

    # -- Output -----------------------------------------------------------

    def print_summary(self) -> None:
        """
        Print a formatted cost summary table to stdout.

        Uses box-drawing characters for a clean visual display.
        """
        if not self._calls:
            print("\n╔══════════════════════════════════════════════════════════════╗")
            print("║   API COST SUMMARY — No API calls recorded                  ║")
            print("╚══════════════════════════════════════════════════════════════╝\n")
            return

        # Header
        print("\n╔══════════════════════════════════════════════════════════════════════════╗")
        print("║                        API COST SUMMARY                                 ║")
        print("╠══════════════════════════════════════════════════════════════════════════╣")

        # Per-model breakdown
        model_stats = self.by_model()
        for model, stats in model_stats.items():
            print(f"║  Model : {model:<56} ║")
            print(f"║    Calls : {stats.call_count:<6}  |  "
                  f"Input: {stats.total_input_tokens:>7,} tok  |  "
                  f"Output: {stats.total_output_tokens:>7,} tok        ║")
            print(f"║    Cost  : ${stats.total_cost_usd:>10.6f}  |  "
                  f"Duration: {stats.total_duration_seconds:>7.2f}s                   ║")
            print("║──────────────────────────────────────────────────────────────────────────║")

        # Totals
        print(f"║  TOTAL   : ${self.total_cost_usd:>10.6f}  |  "
              f"{self.total_tokens:>7,} tokens  |  "
              f"{self.call_count} call(s)                        ║")
        print("╚══════════════════════════════════════════════════════════════════════════╝\n")

    def save(self, path: str) -> None:
        """
        Save a JSON cost report to *path*.

        The parent directory is created automatically if it does not exist.
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        report: Dict[str, Any] = {
            "pipeline_run": self._started_at,
            "total_cost_usd": round(self.total_cost_usd, 8),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_duration_seconds": round(self.total_duration_seconds, 4),
            "call_count": self.call_count,
            "model_breakdown": {
                model: stats.to_dict()
                for model, stats in self.by_model().items()
            },
            "agent_breakdown": list(self.by_agent().values()),
            "calls": [call.to_dict() for call in self._calls],
        }

        with dest.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Return the full report as a dict (useful for testing)."""
        return {
            "pipeline_run": self._started_at,
            "total_cost_usd": round(self.total_cost_usd, 8),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_duration_seconds": round(self.total_duration_seconds, 4),
            "call_count": self.call_count,
            "model_breakdown": {
                model: stats.to_dict()
                for model, stats in self.by_model().items()
            },
            "agent_breakdown": list(self.by_agent().values()),
        }
