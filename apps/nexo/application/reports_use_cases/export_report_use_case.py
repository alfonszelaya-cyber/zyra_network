
from __future__ import annotations
import json as _j

class ExportReportUseCase:
    """Exporta reporte a texto o JSON."""

    def __init__(self, report_engine):
        self._eng = report_engine

    def execute(self, *, report_id,
                fmt="json") -> dict:
        r = self._eng.get(report_id)
        if not r:
            raise KeyError(report_id)
        if fmt == "text":
            lines = [r["report_type"],
                     "empresa: "
                     + r.get("company_id", ""),
                     "periodo: "
                     + r.get("period", "")]
            for k, v in (r.get("data")
                         or {}).items():
                lines.append(str(k) + ": "
                             + str(v))
            return {"report_id": report_id,
                    "format": "text",
                    "content": "\n".join(lines)}
        return {"report_id": report_id,
                "format": "json",
                "content": _j.dumps(r,
                                    default=str,
                                    indent=2)}
