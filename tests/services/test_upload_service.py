from pathlib import Path
from unittest.mock import MagicMock, patch
from services.upload_service import UploadService
from services.confluence_config import ConfluenceConfig, DeploymentType
from services.file_tracker import FileTracker


def _make_cfg(tmp_path) -> ConfluenceConfig:
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.CLOUD
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "u@co.com"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "TEAM"
    return cfg


def test_upload_calls_subprocess(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    tracker = MagicMock(spec=FileTracker)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        svc = UploadService(cfg, tracker)
        results = svc.upload([path])

    assert mock_run.called
    cmd_args = mock_run.call_args[0][0]
    assert str(path) in cmd_args
    assert results[0][1] is True  # success


def test_upload_failure_returns_false(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    tracker = MagicMock(spec=FileTracker)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Auth error")
        svc = UploadService(cfg, tracker)
        results = svc.upload([path])

    assert results[0][1] is False
    assert "Auth error" in results[0][2]


def test_upload_calls_write_sync_state_on_success(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    tracker = MagicMock(spec=FileTracker)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 999\n", stderr="")
        UploadService(cfg, tracker).upload([path])

    tracker.write_sync_state.assert_called_once_with(
        path, {"confluence_id": "999", "confluence_space": "TEAM"}
    )


def test_upload_success_without_page_id_does_not_call_tracker(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    tracker = MagicMock(spec=FileTracker)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Done.\n", stderr="")
        results = UploadService(cfg, tracker).upload([path])

    tracker.write_sync_state.assert_not_called()
    assert results[0][1] is True


def test_progress_callback_called(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    calls = []

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        UploadService(cfg, MagicMock()).upload([path], progress_callback=lambda f, m: calls.append(m))

    assert len(calls) == 2
