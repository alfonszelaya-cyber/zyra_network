"""Workflow contracts."""
from __future__ import annotations

from dataclasses import dataclass

STATE_RUNNING = "RUNNING"
STATE_COMPLETED = "COMPLETED"
STATE_COMPENSATING = "COMPENSATING"
STATE_COMPENSATED = "COMPENSATED"


@dataclass(frozen=True)
class WorkflowRun:
    """Durable run snapshot."""

    run_id: str
    workflow_id: str
    state: str
    steps: tuple[str, ...]
    completed_count: int
    pending_compensations: int
    reason: str | None
