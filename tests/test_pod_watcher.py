"""Tests for PodWatcher."""

from unittest.mock import MagicMock

from restart_controller.pod_watcher import PodWatcher

NAMESPACE = "test-ns"


def _make_pod(name: str, restart_count: int = 0, owner_rs: str | None = None):
    """Create a mock pod object."""
    pod = MagicMock()
    pod.metadata.name = name

    cs = MagicMock()
    cs.restart_count = restart_count
    pod.status.container_statuses = [cs]

    if owner_rs:
        owner = MagicMock()
        owner.kind = "ReplicaSet"
        owner.name = owner_rs
        pod.metadata.owner_references = [owner]
    else:
        pod.metadata.owner_references = []

    return pod


def _make_watcher(on_change: MagicMock | None = None, deployment_for_rs: str | None = None):
    """Create a PodWatcher with mocked APIs."""
    mock_apps = MagicMock()
    mock_core = MagicMock()
    cb = on_change or MagicMock()
    watcher = PodWatcher(NAMESPACE, cb, apps_api=mock_apps, core_api=mock_core)

    if deployment_for_rs:
        rs = MagicMock()
        rs_owner = MagicMock()
        rs_owner.kind = "Deployment"
        rs_owner.name = deployment_for_rs
        rs.metadata.owner_references = [rs_owner]
        mock_apps.read_namespaced_replica_set.return_value = rs

    return watcher, cb


class TestDeletedEvent:
    def test_deleted_pod_triggers_on_change(self):
        watcher, cb = _make_watcher(deployment_for_rs="my-app")
        pod = _make_pod("my-app-abc123", owner_rs="my-app-rs")

        watcher._process_event({"type": "DELETED", "object": pod})

        cb.assert_called_once_with("my-app")

    def test_deleted_pod_cleans_up_restart_counts(self):
        watcher, cb = _make_watcher(deployment_for_rs="my-app")
        pod = _make_pod("my-app-abc123", restart_count=3, owner_rs="my-app-rs")

        # Simulate a prior MODIFIED event to populate restart counts
        watcher._process_event({"type": "MODIFIED", "object": pod})
        assert "my-app-abc123" in watcher._restart_counts

        watcher._process_event({"type": "DELETED", "object": pod})
        assert "my-app-abc123" not in watcher._restart_counts

    def test_deleted_pod_without_deployment_does_not_trigger(self):
        watcher, cb = _make_watcher()
        pod = _make_pod("orphan-pod")

        watcher._process_event({"type": "DELETED", "object": pod})

        cb.assert_not_called()


class TestRestartCountIncrease:
    def test_restart_count_increase_triggers_on_change(self):
        watcher, cb = _make_watcher(deployment_for_rs="my-app")
        pod = _make_pod("my-app-abc123", restart_count=1, owner_rs="my-app-rs")

        # First event sets baseline
        watcher._process_event({"type": "MODIFIED", "object": pod})
        cb.assert_not_called()

        # Second event with increased count triggers
        pod2 = _make_pod("my-app-abc123", restart_count=2, owner_rs="my-app-rs")
        watcher._process_event({"type": "MODIFIED", "object": pod2})
        cb.assert_called_once_with("my-app")

    def test_initial_event_does_not_trigger(self):
        watcher, cb = _make_watcher(deployment_for_rs="my-app")
        pod = _make_pod("my-app-abc123", restart_count=5, owner_rs="my-app-rs")

        watcher._process_event({"type": "MODIFIED", "object": pod})

        cb.assert_not_called()

    def test_no_container_statuses_ignored(self):
        watcher, cb = _make_watcher()
        pod = MagicMock()
        pod.metadata.name = "my-pod"
        pod.status.container_statuses = None

        watcher._process_event({"type": "MODIFIED", "object": pod})

        cb.assert_not_called()
