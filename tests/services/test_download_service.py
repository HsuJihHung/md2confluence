from pathlib import Path
from unittest.mock import MagicMock, patch
from services.download_service import DownloadService, DownloadScope
from services.confluence_config import ConfluenceConfig, DeploymentType
from services.file_tracker import FileTracker


def _make_cfg(tmp_path) -> ConfluenceConfig:
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "u@co.com"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "TEAM"
    return cfg


def test_single_page_uses_pages_command(tmp_path):
    cfg = _make_cfg(tmp_path)
    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        DownloadService(cfg).download(
            page_url="https://co.atlassian.net/wiki/pages/123",
            scope=DownloadScope.SINGLE,
            target_dir=tmp_path,
        )
    cmd = mock_run.call_args[0][0]
    assert "pages" in cmd
    assert "pages-with-descendants" not in " ".join(cmd)


def test_recursive_uses_pages_with_descendants(tmp_path):
    cfg = _make_cfg(tmp_path)
    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        DownloadService(cfg).download(
            page_url="https://co.atlassian.net/wiki/pages/123",
            scope=DownloadScope.RECURSIVE,
            target_dir=tmp_path,
        )
    cmd = mock_run.call_args[0][0]
    assert "pages-with-descendants" in cmd


def test_failure_returns_false(tmp_path):
    cfg = _make_cfg(tmp_path)
    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Not found")
        ok, msg = DownloadService(cfg).download("https://x.com/1", DownloadScope.SINGLE, tmp_path)
    assert ok is False
    assert "Not found" in msg


def test_success_returns_true(tmp_path):
    cfg = _make_cfg(tmp_path)
    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        ok, msg = DownloadService(cfg).download("https://x.com/1", DownloadScope.SINGLE, tmp_path)
    assert ok is True
