"""Kubernetes resource watcher for deployments and pods.

Watches for deployment rollout changes and pod container restarts,
then notifies a callback when a relevant event is detected.
"""

from __future__ import annotations

import logging
from typing import Callable

from kubernetes import client, watch

import restart_controller


class Watcher:
    """Watches Kubernetes deployments and pods for restart-relevant events.

    Holds namespace and API clients as instance state so that watch methods
    only need a callback argument.
    """

    ANNOTATION_PARENT = f"{restart_controller.ANNOTATION_PREFIX}parent"

    def __init__(
        self,
        namespace: str,
        on_change: Callable[[str], None],
        apps_api: client.AppsV1Api | None = None,
        core_api: client.CoreV1Api | None = None,
    ) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._namespace = namespace
        self._on_change = on_change
        self._apps_api = apps_api or client.AppsV1Api()
        self._core_api = core_api or client.CoreV1Api()
        self._rs_to_deployment: dict[str, str | None] = {}

    def watch_deployments(self) -> None:
        """Watch deployments for spec.template changes (rollout triggers).

        Runs indefinitely. When a deployment with restart-controller annotations
        has its pod template modified externally, calls the on_change callback.
        """
        w = watch.Watch()
        template_hashes: dict[str, str] = {}

        self._logger.info("Starting deployment watcher on namespace %s", self._namespace)
        for event in w.stream(self._apps_api.list_namespaced_deployment, namespace=self._namespace):
            event_type = event["type"]
            deployment = event["object"]
            name = deployment.metadata.name
            annotations = self._get_annotations(deployment)

            if not self._has_restart_annotations(annotations):
                continue

            wave = annotations.get(self.ANNOTATION_WAVE, "")
            template_hash = str(deployment.spec.template)
            prev_hash = template_hashes.get(name)
            template_hashes[name] = template_hash

            if event_type == "MODIFIED" and prev_hash is not None and template_hash != prev_hash:
                if not wave:
                    self._logger.info("Deployment %s template changed (external rollout)", name)
                    self._on_change(name)
                else:
                    self._logger.debug("Deployment %s changed by controller (wave %s), skipping", name, wave)

    def watch_pods(self) -> None:
        """Watch pods for container restart count increases.

        Runs indefinitely. When a pod owned by a deployment has a container
        restart, calls the on_change callback with the deployment name.
        """
        w = watch.Watch()
        restart_counts: dict[str, int] = {}

        self._logger.info("Starting pod watcher on namespace %s", self._namespace)
        for event in w.stream(self._core_api.list_namespaced_pod, namespace=self._namespace):
            pod = event["object"]
            pod_name = pod.metadata.name

            if not pod.status or not pod.status.container_statuses:
                continue

            total_restarts = sum(cs.restart_count for cs in pod.status.container_statuses)
            prev = restart_counts.get(pod_name, 0)
            restart_counts[pod_name] = total_restarts

            if total_restarts > prev and prev > 0:
                deployment_name = self._resolve_deployment(pod)
                if deployment_name:
                    self._logger.info(
                        "Pod %s restarted (count %d -> %d), deployment: %s",
                        pod_name,
                        prev,
                        total_restarts,
                        deployment_name,
                    )
                    self._on_change(deployment_name)

    def _resolve_deployment(self, pod: object) -> str | None:
        """Resolve the owning deployment name for a pod via its ReplicaSet owner.

        Results are cached by ReplicaSet name since all pods from the same
        ReplicaSet belong to the same Deployment.
        """
        for owner in pod.metadata.owner_references or []:
            if owner.kind == "ReplicaSet":
                if owner.name in self._rs_to_deployment:
                    return self._rs_to_deployment[owner.name]
                try:
                    rs = self._apps_api.read_namespaced_replica_set(owner.name, self._namespace)
                    for rs_owner in rs.metadata.owner_references or []:
                        if rs_owner.kind == "Deployment":
                            self._rs_to_deployment[owner.name] = rs_owner.name
                            return rs_owner.name
                    self._rs_to_deployment[owner.name] = None
                except client.ApiException:
                    self._logger.warning("Failed to look up ReplicaSet %s", owner.name)
        return None

    @staticmethod
    def _get_annotations(obj: object) -> dict[str, str]:
        """Safely extract annotations from a K8s object."""
        metadata = getattr(obj, "metadata", None)
        if metadata is None:
            return {}
        return metadata.annotations or {}

    @classmethod
    def _has_restart_annotations(cls, annotations: dict[str, str]) -> bool:
        """Check if annotations contain any restart-controller keys."""
        return any(k.startswith(cls.ANNOTATION_PREFIX) for k in annotations)
