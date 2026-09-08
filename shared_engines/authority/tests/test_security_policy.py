"""Proves the SECURITY_POLICY.md guarantees with code."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.authority.root import (
    PersistentRootAuthority,
    RootAuthorityStatus,
)
from shared_engines.common.errors import IntegrityError

MASTER = "cc" * 32


def test_policy_rotation_maintains_verifiable_history(
    tmp_path: Path,
) -> None:
    """Rotations archive every old fingerprint; the latest
    key persists across loads; history stays verifiable."""
    auth = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    signer1, s1 = auth.load_or_create()
    assert s1.status is RootAuthorityStatus.CREATED_NEW
    signer2, s2 = auth.rotate(rotated_by="ciso")
    assert s2.status is RootAuthorityStatus.ROTATED
    signer3, s3 = auth.rotate(rotated_by="ciso")
    assert s3.status is RootAuthorityStatus.ROTATED
    history = auth.historical_fingerprints()
    assert s1.public_pem_fingerprint in history
    assert s2.public_pem_fingerprint in history
    assert s3.public_pem_fingerprint not in history
    signer4, s4 = auth.load_or_create()
    assert s4.status is RootAuthorityStatus.LOADED
    assert s4.public_pem_fingerprint == (
        s3.public_pem_fingerprint
    )
    assert signer4.public_pem == signer3.public_pem


def test_policy_fail_closed_on_wrong_master(
    tmp_path: Path,
) -> None:
    auth = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    auth.load_or_create()
    intruder = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex="dd" * 32
    )
    with pytest.raises(IntegrityError):
        intruder.load_or_create()
    legitimate = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    restored, status = legitimate.load_or_create()
    assert status.status is RootAuthorityStatus.LOADED
    assert restored is not None
