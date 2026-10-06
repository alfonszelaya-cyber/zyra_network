
from __future__ import annotations
from apps.nexo.domain.operations.process_tracking_engine import (
    ProcessTrackingEngine)

class TrackProcessUseCase:
    """Registra evento y devuelve timeline actualizado
    (repara track_process inexistente del viejo)."""

    def __init__(self, tracking):
        self._track = tracking

    def execute(self, *, process_id, event_type,
                actor="", detail="") -> dict:
        ev = self._track.append_event(
            process_id=process_id,
            event_type=event_type, actor=actor,
            detail=detail)
        return {"event": ev,
                "timeline":
                    self._track.get_timeline(
                        process_id),
                "total_events":
                    self._track.event_count(
                        process_id)}
