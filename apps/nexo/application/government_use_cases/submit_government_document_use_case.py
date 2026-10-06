
from __future__ import annotations

class SubmitGovernmentDocumentUseCase:
    """Somete documento oficial con hash de
    integridad y verificacion inmediata."""

    def __init__(self, documents):
        self._docs = documents

    def execute(self, *, institution_id, doc_type,
                title, content) -> dict:
        d = self._docs.register_document(
            institution_id=institution_id,
            doc_type=doc_type, title=title,
            content=content)
        ok = self._docs.verify_document(
            d["doc_id"], content)
        return {"document": d,
                "integrity_verified": ok}
