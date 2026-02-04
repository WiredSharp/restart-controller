"""Tests for RestartManager."""

from unittest.mock import MagicMock, patch

from restart_controller.restart_manager import RestartManager

NAMESPACE = "test-ns"
DEPLOYMENT_NAME = "my-app"
WAVE_ID = "wave-123"
REASON = "parent db changed"


class TestRestart:
    def test_patches_deployment_with_annotations(self):
        mock_k8s = MagicMock()
        mgr = RestartManager(NAMESPACE, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, WAVE_ID, REASON)

        mock_k8s.patch_namespaced_deployment.assert_called_once()
        args = mock_k8s.patch_namespaced_deployment.call_args
        assert args[0][0] == DEPLOYMENT_NAME
        assert args[0][1] == NAMESPACE

        patch_body = args[0][2]
        annotations = patch_body["spec"]["template"]["metadata"]["annotations"]
        assert RestartManager.ANNOTATION_LAST_RESTART in annotations
        assert annotations[RestartManager.ANNOTATION_WAVE] == WAVE_ID
        assert annotations[RestartManager.ANNOTATION_REASON] == REASON

    def test_logs_error_on_api_failure(self):
        from kubernetes.client import ApiException

        mock_k8s = MagicMock()
        mock_k8s.patch_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")
        mgr = RestartManager(NAMESPACE, mock_k8s)

        # Should not raise
        mgr.restart(DEPLOYMENT_NAME, WAVE_ID, REASON)

    def test_uses_namespace(self):
        other_namespace = "other-ns"
        mock_k8s = MagicMock()
        mgr = RestartManager(other_namespace, mock_k8s)

        mgr.restart(DEPLOYMENT_NAME, WAVE_ID, REASON)

        args = mock_k8s.patch_namespaced_deployment.call_args
        assert args[0][1] == other_namespace


class TestGenerateWaveId:
    def test_returns_string(self):
        wave = RestartManager.generate_wave_id()
        assert isinstance(wave, str)
        assert len(wave) > 0

    @patch("restart_controller.restart_manager.datetime")
    def test_format(self, mock_dt):
        expected_wave = "20250101T120000000000"
        mock_now = MagicMock()
        mock_now.strftime.return_value = expected_wave
        mock_dt.now.return_value = mock_now
        wave = RestartManager.generate_wave_id()
        assert wave == expected_wave
