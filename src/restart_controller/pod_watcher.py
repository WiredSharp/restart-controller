"""Watches pods for container restart count increases."""

from __future__ import annotations

from typing import Callable

from kubernetes import client

from .watcher import Watcher


class PodWatcher(Watcher):
    """Detects pod container restarts and resolves the owning deployment.

    Uses a ReplicaSet-to-Deployment cache to avoid redundant API lookups.
    """

    def __init__(
        self,
        namespace: str,
        on_change: Callable[[str], None],
        apps_api: client.AppsV1Api | None = None,
        core_api: client.CoreV1Api | None = None,
    ):
        super().__init__(namespace, on_change)
        self._apps_api = apps_api or client.AppsV1Api()
        self._core_api = core_api or client.CoreV1Api()
        self._restart_counts: dict[str, int] = {}
        self._rs_to_deployment: dict[str, str | None] = {}

    @property
    def _list_func(self) -> Callable[..., object]:
        return self._core_api.list_namespaced_pod

    def _process_event(self, event: dict) -> None:
        event_type = event["type"]
        pod = event["object"]
        pod_name = pod.metadata.name

        if event_type == "DELETED":
            self._restart_counts.pop(pod_name, None)
            deployment_name = self._resolve_deployment(pod)
            if deployment_name:
                self._logger.info(
                    "Pod %s deleted, deployment: %s",
                    pod_name,
                    deployment_name,
                )
                self._on_change(deployment_name)
            return

        if not pod.status or not pod.status.container_statuses:
            return

        total_restarts = sum(cs.restart_count for cs in pod.status.container_statuses)
        prev = self._restart_counts.get(pod_name, 0)
        self._restart_counts[pod_name] = total_restarts

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
