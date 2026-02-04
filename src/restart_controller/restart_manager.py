"""Restart manager: triggers deployment restarts via annotation patches.

Patches deployment annotations to force a rollout restart, using a cooldown
to prevent restart loops.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from kubernetes import client

import restart_controller


class RestartManager:
    ANNOTATION_LAST_RESTART = f"{restart_controller.ANNOTATION_PREFIX}last-restart"
    ANNOTATION_REASON = f"{restart_controller.ANNOTATION_PREFIX}restart-reason"

    COOLDOWN = 60.0

    """Triggers deployment restarts by patching annotations."""

    def __init__(self, namespace: str, apps_api: client.AppsV1Api | None = None) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._namespace = namespace
        self._apps_api = apps_api or client.AppsV1Api()
        self._last_restart: dict[str, float] = {}

    def restart(self, deployment_name: str, reason: str) -> bool:
        """Trigger a rollout restart for a deployment.

        Sets restart-controller annotations on the pod template to force
        Kubernetes to roll out new pods. Skips if the deployment was recently
        restarted (within COOLDOWN seconds).

        Args:
            deployment_name: Name of the deployment to restart.
            reason: Human-readable reason for the restart.

        Returns:
            True if restart was triggered, False if skipped due to cooldown.
        """
        now = time.monotonic()
        last = self._last_restart.get(deployment_name, 0.0)
        if now - last < self.COOLDOWN:
            self._logger.debug(
                "Skipping restart of %s (restarted %.1fs ago)",
                deployment_name,
                now - last,
            )
            return False

        timestamp = datetime.now(timezone.utc).isoformat()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            RestartManager.ANNOTATION_LAST_RESTART: timestamp,
                            RestartManager.ANNOTATION_REASON: reason,
                        }
                    }
                }
            }
        }

        try:
            self._apps_api.patch_namespaced_deployment(deployment_name, self._namespace, patch)
            self._last_restart[deployment_name] = now
            self._logger.info(
                "Restarted deployment %s (reason=%s)",
                deployment_name,
                reason,
            )
            return True
        except client.ApiException as e:
            self._logger.error("Failed to restart deployment %s: %s", deployment_name, e)
            return False
