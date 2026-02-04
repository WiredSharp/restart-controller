"""Restart manager: triggers deployment restarts via annotation patches.

Patches deployment annotations to force a rollout restart, using a wave ID
to allow the watcher to distinguish controller-initiated changes from
external ones and prevent restart loops.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from kubernetes import client

import restart_controller


class RestartManager:
    ANNOTATION_LAST_RESTART = f"{restart_controller.ANNOTATION_PREFIX}last-restart"
    ANNOTATION_WAVE = f"{restart_controller.ANNOTATION_PREFIX}wave"
    ANNOTATION_REASON = f"{restart_controller.ANNOTATION_PREFIX}restart-reason"

    """Triggers deployment restarts by patching annotations."""

    def __init__(self, namespace: str, apps_api: client.AppsV1Api | None = None) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._namespace = namespace
        self._apps_api = apps_api or client.AppsV1Api()

    def restart(self, deployment_name: str, wave_id: str, reason: str) -> None:
        """Trigger a rollout restart for a deployment.

        Sets restart-controller annotations on the pod template to force
        Kubernetes to roll out new pods.

        Args:
            deployment_name: Name of the deployment to restart.
            wave_id: Unique ID for this restart wave (used to prevent loops).
            reason: Human-readable reason for the restart.
        """
        now = datetime.now(timezone.utc).isoformat()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            RestartManager.ANNOTATION_LAST_RESTART: now,
                            RestartManager.ANNOTATION_WAVE: wave_id,
                            RestartManager.ANNOTATION_REASON: reason,
                        }
                    }
                }
            }
        }

        try:
            self._apps_api.patch_namespaced_deployment(deployment_name, self._namespace, patch)
            self._logger.info(
                "Restarted deployment %s (wave=%s, reason=%s)",
                deployment_name,
                wave_id,
                reason,
            )
        except client.ApiException as e:
            self._logger.error("Failed to restart deployment %s: %s", deployment_name, e)

    @staticmethod
    def generate_wave_id() -> str:
        """Generate a unique wave ID based on the current timestamp."""
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
