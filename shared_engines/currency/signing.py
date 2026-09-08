"""Ed25519-signed quotes: portable, third-party verifiable FX.

A signed quote binds issuer, pair, rate and validity window
into a canonical payload signed with the Network key. The
receiving bank verifies offline that the presented rate is
the one Zyra issued - no database access needed.
"""
from __future__ import annotations

from shared_engines.common.serialization import canonical_json_dumps
from shared_engines.currency.contracts import Quote, SignedQuote
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)

QUOTE_FORMAT = "zyra.fxquote.v1"


def quote_canonical_bytes(signed: SignedQuote) -> bytes:
    payload = {
        "format": QUOTE_FORMAT,
        "pair": signed.quote.pair.normalized,
        "rate": str(signed.quote.rate),
        "quoted_at": f"{signed.quote.quoted_at:.6f}",
        "expires_at": f"{signed.quote.expires_at:.6f}",
        "source": signed.quote.source,
        "issuer_zid": signed.issuer_zid,
    }
    return canonical_json_dumps(payload).encode("utf-8")


class QuoteSigner:
    """Signs and verifies FX quotes with the Network key."""

    def __init__(self, signer: Ed25519Signer) -> None:
        self._signer = signer

    def sign(self, quote: Quote, *, issuer_zid: str) -> SignedQuote:
        candidate = SignedQuote(
            quote=quote,
            issuer_zid=issuer_zid,
            signature=b"",
            signer_public_pem=self._signer.public_pem,
        )
        data = quote_canonical_bytes(candidate)
        signature = self._signer.sign(data)
        return SignedQuote(
            quote=quote,
            issuer_zid=issuer_zid,
            signature=signature,
            signer_public_pem=self._signer.public_pem,
        )

    @staticmethod
    def verify(signed: SignedQuote) -> bool:
        data = quote_canonical_bytes(signed)
        verifier = Ed25519Verifier(signed.signer_public_pem)
        return verifier.verify(data, signed.signature)
