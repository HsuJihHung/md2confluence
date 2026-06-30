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
    assert "--no-generated-by" in cmd_args
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

    assert len(calls) == 3


def test_upload_with_macro_options(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    cfg.mermaid_mode = "macro"
    cfg.plantuml_mode = "macro"

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        UploadService(cfg, MagicMock()).upload([path])

    cmd_args = mock_run.call_args[0][0]
    assert "--no-render-mermaid" in cmd_args
    assert "--no-render-plantuml" in cmd_args


def test_upload_with_parent_page_id(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        UploadService(cfg, MagicMock()).upload([path], parent_page_id="12345")

    cmd_args = mock_run.call_args[0][0]
    assert "--root-page" in cmd_args
    assert "12345" in cmd_args


def test_upload_uses_file_specific_space_key(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    tracker = MagicMock(spec=FileTracker)
    
    mock_info = MagicMock()
    mock_info.confluence_space = "CUSTOM_SPACE"
    tracker._inspect.return_value = mock_info

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        UploadService(cfg, tracker).upload([path])

    assert mock_run.called
    env_passed = mock_run.call_args[1]["env"]
    assert env_passed["CONFLUENCE_SPACE_KEY"] == "CUSTOM_SPACE"


def test_upload_fetches_and_saves_full_page_details(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    cfg.fetch_page_details = MagicMock(return_value={
        "confluence_id": "999",
        "confluence_space": "TEAM",
        "confluence_page_name": "Fetched Title",
        "confluence_url": "https://co.atlassian.net/wiki/spaces/TEAM/pages/999"
    })
    tracker = MagicMock(spec=FileTracker)

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 999\n", stderr="")
        UploadService(cfg, tracker).upload([path])

    cfg.fetch_page_details.assert_called_once_with("999")
    tracker.write_sync_state.assert_called_once_with(
        path, {
            "confluence_id": "999",
            "confluence_space": "TEAM",
            "confluence_page_name": "Fetched Title",
            "confluence_url": "https://co.atlassian.net/wiki/spaces/TEAM/pages/999"
        }
    )


def test_upload_resolves_space_from_parent_page_id(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    cfg.fetch_space_key_for_page = MagicMock(return_value="RESOLVED_SPACE")
    tracker = MagicMock(spec=FileTracker)
    
    mock_info = MagicMock()
    mock_info.confluence_space = ""
    mock_info.confluence_id = ""
    tracker._inspect.return_value = mock_info

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        UploadService(cfg, tracker).upload([path], parent_page_id="parent123")

    cfg.fetch_space_key_for_page.assert_called_once_with("parent123")
    env_passed = mock_run.call_args[1]["env"]
    assert env_passed["CONFLUENCE_SPACE_KEY"] == "RESOLVED_SPACE"


def test_upload_resolves_space_from_existing_page_id(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    cfg.fetch_space_key_for_page = MagicMock(return_value="RESOLVED_EXISTING_SPACE")
    tracker = MagicMock(spec=FileTracker)
    
    mock_info = MagicMock()
    mock_info.confluence_space = ""
    mock_info.confluence_id = "existing123"
    tracker._inspect.return_value = mock_info

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Page ID: 111\n", stderr="")
        UploadService(cfg, tracker).upload([path])

    cfg.fetch_space_key_for_page.assert_called_once_with("existing123")
    env_passed = mock_run.call_args[1]["env"]
    assert env_passed["CONFLUENCE_SPACE_KEY"] == "RESOLVED_EXISTING_SPACE"


