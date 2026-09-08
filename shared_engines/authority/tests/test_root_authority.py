from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.authority.root import (
    PersistentRootAuthority,
    RootAuthorityStatus,
)
from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
)

MASTER = "aa" * 32
OTHER_MASTER = "bb" * 32


def test_first_boot_creates_then_loads_same_key(
    tmp_path: Path,
) -> None:
    auth = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    signer, status = auth.load_or_create()
    assert status.status is RootAuthorityStatus.CREATED_NEW
    fp = status.public_pem_fingerprint
    signer2, status2 = auth.load_or_create()
    assert status2.status is RootAuthorityStatus.LOADED
    assert status2.public_pem_fingerprint == fp
    assert signer2.public_pem == signer.public_pem


def test_wrong_master_fails_closed(tmp_path: Path) -> None:
    auth = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    auth.load_or_create()
    attacker = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=OTHER_MASTER
    )
    with pytest.raises(IntegrityError):
        attacker.load_or_create()


def test_master_key_validation(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        PersistentRootAuthority(
            data_dir=tmp_path, master_key_hex="tooshort"
        )
    with pytest.raises(ConfigurationError):
        PersistentRootAuthority(
            data_dir=tmp_path, master_key_hex="zz" * 32
        )


def test_rotation_archives_old_fingerprint(
    tmp_path: Path,
) -> None:
    auth = PersistentRootAuthority(
        data_dir=tmp_path, master_key_hex=MASTER
    )
    signer1, s1 = auth.load_or_create()
    signer2, s2 = auth.rotate(rotated_by="founder")
    assert s2.status is RootAuthorityStatus.ROTATED
    assert s2.public_pem_fingerprint != s1.public_pem_fingerprint
    assert (
        s1.public_pem_fingerprint
        in auth.historical_fingerprints()
    )
    signer3, s3 = auth.load_or_create()
    assert s3.status is RootAuthorityStatus.LOADED
    assert s3.public_pem_fingerprint == s2.public_pem_fingerprint
    assert signer2.public_pem != signer1.public_pem
