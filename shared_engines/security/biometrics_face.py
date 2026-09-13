"""Real face provider: InsightFace buffalo_l (ArcFace)
+ heuristic PAD liveness.

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

Liveness (heuristic PAD, hardening v3):
- liveness_supported = True
- Analyzes the DETECTED FACE CROP (not the background):
  1. Moire signature via FFT (screens re-photographed)
  2. Texture via Laplacian variance (flat prints)
  3. Saturation (printed-paper whitewash)
- Verdict is conservative: False ONLY on clear attack
  signals (strong moire, or 2+ weak indicators). Real
  users in poor conditions may be asked to retry with
  better light — never silently approved.
- HONEST LIMITS: heuristic PAD catches print/screen
  attacks, the common ones. It is NOT certified against
  3D masks or deepfake video injection (that requires an
  iBeta-certified vendor PAD in a later phase).

Import self-healing: insightface bundles a face3d/mesh
Cython accessory compiled at install time against
whatever numpy the build env had. This provider never
uses face3d/mesh, so if that accessory fails to load
(binary mismatch), it is replaced by an inert stub:
detection and embedding are unaffected.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
import unittest

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

# Heuristic PAD thresholds (calibrated defaults)
_MOIRE_STRONG = 40.0
_MOIRE_WEAK = 12.0
_TEXTURE_LOW = 25.0
_SAT_LOW = 20.0
_CROP = 256


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


# =====================================================
# Heuristic PAD (presentation attack detection)
# =====================================================


def laplacian_variance(gray) -> float:
    """Texture energy of the crop (blurred flat
    prints score very low; real skin scores high)."""
    import cv2

    return float(
        cv2.Laplacian(gray, cv2.CV_64F).var()
    )


def moire_strength(gray) -> float:
    """Peak-to-median ratio of the FFT magnitude in
    the mid-frequency band. Re-photographed screens
    produce strong isolated periodic peaks (moire)."""
    import numpy as np

    g = gray.astype(np.float32)
    f = np.fft.fftshift(np.fft.fft2(g))
    mag = np.abs(f) + 1e-6
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    r = np.sqrt(
        (yy - cy) ** 2 + (xx - cx) ** 2
    )
    band = (r >= 20) & (r <= 110)
    bandmag = mag[band]
    if bandmag.size == 0:
        return 0.0
    peak = float(bandmag.max())
    med = float(np.median(bandmag)) + 1e-6
    return peak / med


def mean_saturation(bgr) -> float:
    """Mean HSV saturation. Printed-paper whitewash
    drains color; real skin keeps it."""
    import cv2

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return float(hsv[..., 1].mean())


def liveness_verdict(bgr) -> tuple[bool, list]:
    """Conservative verdict: False ONLY on clear
    attack signals. Returns (is_live, reasons)."""
    import cv2

    h, w = bgr.shape[:2]
    if max(h, w) > _CROP:
        s = _CROP / float(max(h, w))
        bgr = cv2.resize(
            bgr,
            (
                max(1, int(w * s)),
                max(1, int(h * s)),
            ),
        )
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    var = laplacian_variance(gray)
    moire = moire_strength(gray)
    sat = mean_saturation(bgr)
    reasons: list = []
    weak = 0
    if moire >= _MOIRE_STRONG:
        reasons.append(
            f"moire_strong({moire:.1f})"
        )
    elif moire >= _MOIRE_WEAK:
        reasons.append(
            f"moire_weak({moire:.1f})"
        )
        weak += 1
    if var < _TEXTURE_LOW:
        reasons.append(
            f"low_texture({var:.1f})"
        )
        weak += 1
    if sat < _SAT_LOW:
        reasons.append(
            f"low_saturation({sat:.1f})"
        )
        weak += 1
    strong = any(
        r.startswith("moire_strong")
        for r in reasons
    )
    if strong or weak >= 2:
        return False, reasons
    return True, reasons


# =====================================================
# Provider
# =====================================================


class InsightFaceProvider:
    """Real face analysis over the BiometricProvider
    surface. Heavy dependencies are imported lazily so
    the base network keeps working without them."""

    name = "insightface-buffalo_l"
    modality = "face"
    liveness_supported = True

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
            f" (mesh: {mesh_mode},"
            " pad: heuristic)"
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

    def check_liveness(
        self, image: bytes
    ) -> bool:
        """Heuristic PAD over the detected face crop.
        False = clear presentation-attack signals."""
        img = self._decode(image)
        try:
            faces = self._app.get(img)
        except Exception:
            faces = []
        if not faces:
            return False
        subject = max(
            faces,
            key=lambda f: float(f.bbox[2] - f.bbox[0])
            * float(f.bbox[3] - f.bbox[1]),
        )
        x1, y1, x2, y2 = [
            int(v) for v in subject.bbox
        ]
        h, w = img.shape[:2]
        mx = int(0.2 * (x2 - x1))
        my = int(0.2 * (y2 - y1))
        x1 = max(0, x1 - mx)
        y1 = max(0, y1 - my)
        x2 = min(w, x2 + mx)
        y2 = min(h, y2 + my)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            return False
        live, reasons = liveness_verdict(crop)
        if not live:
            print(
                "PAD REJECT:",
                ",".join(reasons),
            )
        return live

    def compare(
        self,
        a: TemplateVector,
        b: TemplateVector,
    ) -> float:
        return cosine_similarity(a, b)


# =====================================================
# Model-free PAD tests (deterministic synthetic
# images). These run in CI without downloading the
# face model.
# =====================================================


class LivenessHeuristicTests(unittest.TestCase):
    def _moire_image(self):
        import cv2
        import numpy as np

        x = np.arange(_CROP)
        y = np.arange(_CROP)
        xx, yy = np.meshgrid(x, y)
        pat = 128 + 45 * np.sin(
            2 * np.pi * xx / 6.0
        ) * np.cos(2 * np.pi * yy / 6.0)
        return np.stack(
            [pat] * 3, axis=-1
        ).astype("uint8")

    def _natural_image(self):
        import numpy as np

        np.random.seed(7)
        skin = np.zeros(
            (_CROP, _CROP, 3), dtype=np.int16
        )
        skin[..., 0] = 120
        skin[..., 1] = 150
        skin[..., 2] = 190
        noise = np.random.randint(
            -18, 19, (_CROP, _CROP, 1)
        ).astype(np.int16)
        return np.clip(
            skin + noise, 0, 255
        ).astype("uint8")

    def test_moire_flagged_as_attack(self) -> None:
        live, reasons = liveness_verdict(
            self._moire_image()
        )
        self.assertFalse(live)
        self.assertTrue(
            any(
                r.startswith("moire_strong")
                for r in reasons
            )
        )

    def test_natural_passes(self) -> None:
        live, _reasons = liveness_verdict(
            self._natural_image()
        )
        self.assertTrue(live)

    def test_flat_blur_gray_flagged(self) -> None:
        import numpy as np

        flat = np.full(
            (_CROP, _CROP, 3), 118, dtype=np.uint8
        )
        live, reasons = liveness_verdict(flat)
        self.assertFalse(live)
        self.assertGreaterEqual(len(reasons), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
