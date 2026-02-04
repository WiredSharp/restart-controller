"""Tests for RestartManager."""

from unittest.mock import MagicMock

from restart_controller.restart_manager import RestartManager

NAMESPACE = "test-ns"
DEPLOYMENT_NAME = "my-app"
REASON = "parent db changed"


class TestRestart:
    def test_patches_deployment_with_annotations(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, REASON)

        mock_k8s.patch_namespaced_deployment.assert_called_once()
        args = mock_k8s.patch_namespaced_deployment.call_args
        assert args[0][0] == DEPLOYMENT_NAME
        assert args[0][1] == NAMESPACE

        patch_body = args[0][2]
        annotations = patch_body["spec"]["template"]["metadata"]["annotations"]
        assert RestartManager.ANNOTATION_LAST_RESTART in annotations
        assert annotations[RestartManager.ANNOTATION_REASON] == REASON

    def test_logs_error_on_api_failure(self):
        from kubernetes.client import ApiException

        mock_k8s = MagicMock()
        mock_k8s.patch_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, REASON)

    def test_uses_namespace(self):
        other_namespace = "other-ns"
        mock_k8s = MagicMock()
        mgr = RestartManager(other_namespace, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, REASON)

        args = mock_k8s.patch_namespaced_deployment.call_args
        assert args[0][1] == other_namespace

    def test_returns_true_on_success(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        result = mgr.restart(DEPLOYMENT_NAME, REASON)

        assert result is True

    def test_returns_false_on_api_failure(self):
        from kubernetes.client import ApiException

        mock_k8s = MagicMock()
        mock_k8s.patch_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")
        mgr = RestartManager(NAMESPACE, mock_k8s)

        result = mgr.restart(DEPLOYMENT_NAME, REASON)

        assert result is False


class TestCooldown:
    def test_skips_restart_within_cooldown(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, REASON)
        result = mgr.restart(DEPLOYMENT_NAME, REASON)

        assert result is False
        assert mock_k8s.patch_namespaced_deployment.call_count == 1

    def test_allows_restart_after_cooldown(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, REASON)

        mgr._last_restart[DEPLOYMENT_NAME] -= RestartManager.COOLDOWN + 1

        result = mgr.restart(DEPLOYMENT_NAME, REASON)

        assert result is True
        assert mock_k8s.patch_namespaced_deployment.call_count == 2

    def test_different_deployments_not_affected(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart("app1", REASON)
        result = mgr.restart("app2", REASON)

        assert result is True
        assert mock_k8s.patch_namespaced_deployment.call_count == 2
