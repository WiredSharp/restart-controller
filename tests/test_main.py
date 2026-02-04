"""Tests for the Controller class in main.py."""

from unittest.mock import MagicMock

from restart_controller.dependency_tree import DependencyTree
from restart_controller.main import Controller
from restart_controller.watcher import Watcher

NAMESPACE = "test-ns"
DB = "db"
API = "api"
WORKER = "worker"
FRONTEND = "frontend"


def _make_deployment(name: str, annotations: dict[str, str] | None = None):
    """Create a mock deployment object."""
    dep = MagicMock()
    dep.metadata.name = name
    dep.metadata.annotations = annotations
    return dep


def _make_controller(apps_api: MagicMock) -> Controller:
    """Create a Controller with mocked APIs."""
    mock_k8s_core = MagicMock()
    return Controller(NAMESPACE, apps_api, mock_k8s_core)


class TestBuildTree:
    def test_empty_namespace(self):
        mock_k8s_client = MagicMock()
        mock_k8s_client.list_namespaced_deployment.return_value.items = []

        ctrl = _make_controller(mock_k8s_client)
        tree = ctrl.build_tree()
        assert tree.get_children("anything") == set()

    def test_builds_tree_from_annotations(self):
        deps = [
            _make_deployment(DB, {}),
            _make_deployment(API, {Watcher.ANNOTATION_PARENT: DB}),
            _make_deployment(FRONTEND, {Watcher.ANNOTATION_PARENT: API}),
        ]
        mock_k8s_client = MagicMock()
        mock_k8s_client.list_namespaced_deployment.return_value.items = deps

        ctrl = _make_controller(mock_k8s_client)
        tree = ctrl.build_tree()
        assert tree.get_children(DB) == {API}
        assert tree.get_children(API) == {FRONTEND}
        assert tree.get_descendants(DB) == frozenset({API, FRONTEND})

    def test_multiple_children(self):
        deps = [
            _make_deployment(DB, {}),
            _make_deployment(API, {Watcher.ANNOTATION_PARENT: DB}),
            _make_deployment(WORKER, {Watcher.ANNOTATION_PARENT: DB}),
        ]
        mock_k8s_client = MagicMock()
        mock_k8s_client.list_namespaced_deployment.return_value.items = deps

        ctrl = _make_controller(mock_k8s_client)
        tree = ctrl.build_tree()
        assert tree.get_children(DB) == {API, WORKER}

    def test_no_annotations(self):
        deps = [
            _make_deployment("app1", {}),
            _make_deployment("app2", None),
        ]
        mock_k8s_client = MagicMock()
        mock_k8s_client.list_namespaced_deployment.return_value.items = deps

        ctrl = _make_controller(mock_k8s_client)
        tree = ctrl.build_tree()
        assert tree.get_children("app1") == set()


class TestOnChange:
    def _make_controller_with_tree(self, tree: DependencyTree) -> Controller:
        """Create a controller whose build_tree returns the given tree."""
        mock_k8s_client = MagicMock()
        mock_k8s_core = MagicMock()
        ctrl = Controller(NAMESPACE, mock_k8s_client, mock_k8s_core)
        ctrl.build_tree = lambda: tree  # type: ignore[assignment]
        return ctrl

    def test_cascades_restart_to_children(self):
        tree = DependencyTree()
        tree.add(DB, [API, WORKER])
        ctrl = self._make_controller_with_tree(tree)

        ctrl._on_change(DB)

        assert ctrl._restart_mgr._apps_api.patch_namespaced_deployment.call_count == 2

    def test_no_restart_for_leaf(self):
        tree = DependencyTree()
        tree.add(DB, [API])
        ctrl = self._make_controller_with_tree(tree)

        ctrl._on_change(API)

        ctrl._restart_mgr._apps_api.patch_namespaced_deployment.assert_not_called()

    def test_transitive_cascade(self):
        tree = DependencyTree()
        tree.add(DB, [API])
        tree.add(API, [FRONTEND])
        ctrl = self._make_controller_with_tree(tree)

        ctrl._on_change(DB)

        assert ctrl._restart_mgr._apps_api.patch_namespaced_deployment.call_count == 2
