"""
Provider-neutral deployment lifecycle state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock


class DeploymentState(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class Deployment:
    deployment_id: str
    version: str
    environment: str
    state: DeploymentState = (
        DeploymentState.PENDING
    )
    created_at: str = field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        ).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        ).isoformat()
    )
    error: str | None = None


class DeploymentManager:
    """Thread-safe deployment state manager."""

    _ALLOWED = {
        DeploymentState.PENDING: {
            DeploymentState.VALIDATING,
            DeploymentState.FAILED,
        },
        DeploymentState.VALIDATING: {
            DeploymentState.DEPLOYING,
            DeploymentState.FAILED,
        },
        DeploymentState.DEPLOYING: {
            DeploymentState.ACTIVE,
            DeploymentState.FAILED,
        },
        DeploymentState.ACTIVE: {
            DeploymentState.ROLLED_BACK,
        },
        DeploymentState.FAILED: {
            DeploymentState.ROLLED_BACK,
        },
        DeploymentState.ROLLED_BACK: set(),
    }

    def __init__(self) -> None:
        self._deployments: dict[
            str,
            Deployment,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        deployment_id: str,
        version: str,
        environment: str,
    ) -> Deployment:
        if not deployment_id.strip():
            raise ValueError(
                "deployment_id is required"
            )

        if not version.strip():
            raise ValueError(
                "version is required"
            )

        if not environment.strip():
            raise ValueError(
                "environment is required"
            )

        with self._lock:
            if deployment_id in self._deployments:
                raise ValueError(
                    f"deployment already exists: "
                    f"{deployment_id}"
                )

            deployment = Deployment(
                deployment_id=deployment_id,
                version=version,
                environment=environment,
            )

            self._deployments[
                deployment_id
            ] = deployment

            return deployment

    def transition(
        self,
        deployment_id: str,
        target: DeploymentState,
        error: str | None = None,
    ) -> Deployment:
        with self._lock:
            deployment = self._deployments[
                deployment_id
            ]

            if target not in self._ALLOWED[
                deployment.state
            ]:
                raise ValueError(
                    "invalid deployment transition: "
                    f"{deployment.state.value} -> "
                    f"{target.value}"
                )

            deployment.state = target
            deployment.error = error
            deployment.updated_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return deployment

    def get(
        self,
        deployment_id: str,
    ) -> Deployment | None:
        with self._lock:
            return self._deployments.get(
                deployment_id
            )

    def snapshot(
        self,
    ) -> tuple[Deployment, ...]:
        with self._lock:
            return tuple(
                self._deployments.values()
            )


__all__ = [
    "Deployment",
    "DeploymentManager",
    "DeploymentState",
]
