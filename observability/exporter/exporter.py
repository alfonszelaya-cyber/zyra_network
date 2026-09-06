from __future__ import annotations

import json
from typing import Any, Iterable


class ObservationExporter:
    def export(
        self,
        records: Iterable[dict[str, Any]],
    ) -> str:

        raise NotImplementedError


class JSONObservationExporter(
    ObservationExporter
):
    def export(
        self,
        records: Iterable[dict[str, Any]],
    ) -> str:

        return json.dumps(
            list(records),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )


class NDJSONObservationExporter(
    ObservationExporter
):
    def export(
        self,
        records: Iterable[dict[str, Any]],
    ) -> str:

        return "\n".join(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            for record in records
        )


__all__ = [
    "ObservationExporter",
    "JSONObservationExporter",
    "NDJSONObservationExporter",
]
