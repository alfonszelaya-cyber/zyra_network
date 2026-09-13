"""Real face provider: InsightFace buffalo_l (ArcFace).

Production face-recognition engine that plugs into the
BiometricProvider surface defined in
shared_engines/security/biometrics.py. It is loaded by
the kernel only when the environment variable
ZYRA_BIOMETRICS_PROVIDER=insightface is set. Without it,
the network stays fail-closed.

Behavior (production, honest):
- Detection: SCRFD (bundled in buffalo_l pack)
- Template: 512-dim ArcFace embedding, L2-normalized
- No face image is ever stored: the engine seals only
  the numeric template (AES-256-GCM)
- Unreadable image or NO FACE FOUND -> TemplateQualityError
  (fail-closed: the pipeline refuses, never guesses)
- Several faces in frame -> the largest one is the subject
- Liveness: NOT claimed in this phase
  (liveness_supported=False). With require_liveness=True
  (the kernel policy), every strong match routes to human
  review instead of auto-approving.

Import self-healing: insightface bundles a face3d/mesh
Cython accessory compiled at install time against
whatever numpy the build env had. This provider never
uses face3d/mesh, so if that accessory fails to load
(binary mismatch), it is replaced by an inert stub:
detection and embedding are unaffected and the import
becomes ABI-proof.
"""
from __future__ import annotations

import importlib
import os
import sys
import types

from shared_engines.security.biometrics import (
    ProviderError,
    TemplateQualityError,
    TemplateVector,
    cosine_similarity,
)

_MAX_SIDE = 2000
_DET_SIZE = (640, 640)
_MESH_CYTHON = (
    "insightface.thirdparty.face3d.mesh.cython"
)


def _ensure_mesh_importable() -> str:
    """Returns 'native' if the mesh accessory loads,
    'stubbed' if it had to be replaced by an inert
    dummy. Detection/embedding are unaffected either
    way."""
    try:
        importlib.import_module(_MESH_CYTHON)
        return "native"
    except Exception:
        stub = types.ModuleType(_MESH_CYTHON)
        stub.mesh_core_cython = None
        sys.modules[_MESH_CYTHON] = stub
        return "stubbed"


class InsightFaceProvider:
    """Real face analysis over the BiometricProvider
    surface. Heavy dependencies are imported lazily so
    the base network keeps working without them."""

    name = "insightface-buffalo_l"
    modality = "face"
    liveness_supported = False

    def __init__(
        self, models_dir: str | None = None
    ) -> None:
        mesh_mode = _ensure_mesh_importable()
        try:
            import cv2  # noqa: F401
            import numpy as np  # noqa: F401
            from insightface.app import FaceAnalysis
        except Exception as exc:
            raise ProviderError(
                "face engine dependencies missing"
                f" ({exc}); install them or keep"
                " ZYRA_BIOMETRICS_PROVIDER"
                "=fail-closed"
            ) from exc
        self._cv2 = cv2
        self._np = np
        root = (
            models_dir
            if models_dir is not None
            else os.environ.get(
                "ZYRA_BIOMETRICS_MODELS_DIR"
            )
            or None
        )
        try:
            self._app = FaceAnalysis(
                name="buffalo_l",
                root=root,
                providers=[
                    "CPUExecutionProvider"
                ],
            )
            self._app.prepare(
                ctx_id=-1, det_size=_DET_SIZE
            )
        except Exception as exc:
            raise ProviderError(
                "face model could not be loaded:"
                f" {exc}"
            ) from exc
        print(
            "FACE PROVIDER READY"
            f" (mesh: {mesh_mode})"
        )

    def _decode(
        self, image: bytes
    ) -> Any:
        if not isinstance(
            image, (bytes, bytearray)
        ) or len(image) == 0:
            raise TemplateQualityError(
                "image is empty"
            )
        buf = self._np.frombuffer(
            bytes(image), dtype=self._np.uint8
        )
        img = self._cv2.imdecode(
            buf, self._cv2.IMREAD_COLOR
        )
        if img is None:
            raise TemplateQualityError(
                "image is not decodable"
                " (jpeg/png expected)"
            )
        h, w = img.shape[:2]
        longest = max(int(h), int(w))
        if longest > _MAX_SIDE:
            scale = _MAX_SIDE / float(longest)
            img = self._cv2.resize(
                img,
                (
                    max(1, int(w * scale)),
                    max(1, int(h * scale)),
                ),
            )
        return img

    def extract_template(
        self, image: bytes
    ) -> TemplateVector:
        img = self._decode(image)
        try:
            faces = self._app.get(img)
        except Exception as exc:
            raise ProviderError(
                f"face analysis failed: {exc}"
            ) from exc
        if faces is None or len(faces) == 0:
            raise TemplateQualityError(
                "no face detected in image"
            )
        subject = max(
            faces,
            key=lambda f: float(f.bbox[2] - f.bbox[0])
            * float(f.bbox[3] - f.bbox[1]),
        )
        emb = self._np.asarray(
            subject.embedding, dtype=self._np.float64
        )
        norm = float(self._np.sqrt((emb * emb).sum()))
        if norm <= 0.0 or not self._np.isfinite(
            norm
        ):
            raise TemplateQualityError(
                "face embedding is degenerate"
            )
        normalized = emb / norm
        return tuple(
            float(x) for x in normalized
        )

    def compare(
        self,
        a: TemplateVector,
        b: TemplateVector,
    ) -> float:
        return cosine_similarity(a, b)

    def check_liveness(
        self, image: bytes
    ) -> bool:
        """Honest default until active anti-spoofing
        lands: never claim liveness."""
        return False
