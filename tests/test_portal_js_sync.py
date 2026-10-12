"""Las dos copias del JS del portal deben mantenerse byte-identicas."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_portal_js_sincronizados():
    canonico = ROOT / "portal" / "verificar.js"
    copia = ROOT / "public" / "app.js"
    assert canonico.read_bytes() == copia.read_bytes(), (
        "verificar.js y app.js divergieron."
        " Actualizar desde el canonico portal/verificar.js"
    )
