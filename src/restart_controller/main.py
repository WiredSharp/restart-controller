"""Entry point and coordinator for the restart controller.

Loads kubeconfig, builds the dependency tree from deployment annotations,
starts watchers, and orchestrates cascading restarts.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from kubernetes import client, config

from .dependency_tree import DependencyTree
from .logging_config import setup_logging
from .pod_watcher import PodWatcher
from .restart_manager import RestartManager
from .watcher import Watcher


class Controller:
    """Coordinates watchers and restart manager to cascade restarts."""

    DEFAULT_NAMESPACE = "default"

    def __init__(self, namespace: str, apps_api: client.AppsV1Api, core_api: client.CoreV1Api) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._namespace = namespace
        self._apps_api = apps_api
        self._restart_mgr = RestartManager(namespace, apps_api)
        self._pod_watcher = PodWatcher(namespace, self._on_change, apps_api=apps_api, core_api=core_api)

    def build_tree(self) -> DependencyTree:
        """Build the dependency tree by reading annotations from all deployments."""
        tree = DependencyTree()
        deployments = self._apps_api.list_namespaced_deployment(self._namespace)

        children_by_parent: dict[str, list[str]] = {}
        for dep in deployments.items:
            annotations = dep.metadata.annotations or {}
            parent = annotations.get(Watcher.ANNOTATION_PARENT)
            if parent:
                children_by_parent.setdefault(parent, []).append(dep.metadata.name)

        for parent, children in children_by_parent.items():
            tree.add(parent, children)

        self._logger.info("Built dependency tree: %s", {p: list(c) for p, c in children_by_parent.items()})
        return tree

    def _on_change(self, deployment_name: str) -> None:
        """Handle a deployment change event: rebuild tree and cascade restarts."""
        self._logger.info("Handling change for deployment %s", deployment_name)
        tree = self.build_tree()
        restart_set = tree.compute_restart_set({deployment_name})

        if not restart_set:
            self._logger.info("No children to restart for %s", deployment_name)
            return

        reason = f"parent {deployment_name} changed"
        self._logger.info("Restarting %d deployments: %s", len(restart_set), restart_set)
        for dep in restart_set:
            self._restart_mgr.restart(dep, reason)

    def run(self) -> None:
        """Start watcher thread and wait for shutdown signal."""
        stop = threading.Event()

        def shutdown(signum: int, frame: object) -> None:
            self._logger.info("Received signal %d, shutting down", signum)
            stop.set()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        pod_thread = threading.Thread(
            target=self._pod_watcher.watch,
            daemon=True,
            name="pod-watcher",
        )

        pod_thread.start()
        self._logger.info("Pod watcher started")

        stop.wait()
        self._logger.info("Controller stopped")


def main() -> None:
    setup_logging()

    namespace = sys.argv[1] if len(sys.argv) > 1 else Controller.DEFAULT_NAMESPACE

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    apps_api = client.AppsV1Api()
    core_api = client.CoreV1Api()

    controller = Controller(namespace, apps_api, core_api)
    controller.run()


if __name__ == "__main__":
    main()
