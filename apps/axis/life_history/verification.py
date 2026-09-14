"""Life History verification - third-party surface."""
from __future__ import annotations

from apps.axis.life_history.store import (
    LifeHistoryStore,
)


def verify_birth(
    store: LifeHistoryStore,
    birth_id: str,
    *,
    claimed_cert_hash: str,
) -> dict[str, object]:
    birth = store.get_birth(birth_id)
    chain_ok, count = (
        store.births_chain_verify()
    )
    matches = (
        str(birth["cert_hash"])
        == claimed_cert_hash.strip().lower()
    )
    return {
        "birth_id": birth_id,
        "exists": True,
        "active": (
            birth["status"] == "active"
        ),
        "hash_matches": matches,
        "chain_verified": chain_ok,
        "chain_size": count,
        "valid": bool(
            matches
            and chain_ok
            and birth["status"]
            == "active"
        ),
    }


def person_history_summary(
    store: LifeHistoryStore,
    person_id: str,
) -> dict[str, object]:
    person = store.get_person(person_id)
    events = store.events_of(person_id)
    return {
        "person_id": person_id,
        "status": person["status"],
        "zid_bound": (
            person["zid"] is not None
        ),
        "events": len(events),
        "events_verified": (
            store.events_verify(person_id)
        ),
    }
