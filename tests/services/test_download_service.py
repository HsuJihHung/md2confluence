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


def test_write_frontmatter_false_skips_frontmatter(tmp_path):
    cfg = _make_cfg(tmp_path)
    svc = DownloadService(cfg, MagicMock(spec=FileTracker))

    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        with patch.object(svc, "_write_frontmatter_for_new_files") as mock_fm:
            svc.download("https://x.com/1", DownloadScope.SINGLE, tmp_path, write_frontmatter=False)
            mock_fm.assert_not_called()


def test_progress_callback_called(tmp_path):
    cfg = _make_cfg(tmp_path)
    calls = []

    with patch("services.download_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        DownloadService(cfg, MagicMock()).download(
            "https://x.com/1",
            DownloadScope.SINGLE,
            tmp_path,
            progress_callback=lambda msg: calls.append(msg),
        )

    assert len(calls) == 2


def test_download_only_updates_new_or_modified_files(tmp_path):
    cfg = _make_cfg(tmp_path)
    
    # Create an existing markdown file in target directory without confluence_id
    existing_file = tmp_path / "existing.md"
    existing_file.write_text("# Existing Page\n", encoding="utf-8")
    
    # We will simulate cme writing a new file when we call download
    def mock_subprocess_run(cmd, env, **kwargs):
        new_file = tmp_path / "new_download.md"
        new_file.write_text("# New Download\n", encoding="utf-8")
        return MagicMock(returncode=0, stdout="Done", stderr="")
        
    tracker = FileTracker()
    svc = DownloadService(cfg, tracker)
    
    with patch("services.download_service.subprocess.run", side_effect=mock_subprocess_run):
        ok, msg = svc.download(
            page_url="https://co.atlassian.net/wiki/pages/123",
            scope=DownloadScope.SINGLE,
            target_dir=tmp_path,
            write_frontmatter=True,
        )
        
    assert ok is True
    
    # The existing file should NOT be touched (it should still not have frontmatter/confluence_url)
    existing_fm = tracker.read_frontmatter(existing_file)
    assert "confluence_url" not in existing_fm
    
    # The new file should have the frontmatter updated
    new_fm = tracker.read_frontmatter(tmp_path / "new_download.md")
    assert new_fm.get("confluence_url") == "https://co.atlassian.net/wiki/pages/123"


def test_download_updates_ids_from_lockfile(tmp_path):
    import json
    cfg = _make_cfg(tmp_path)
    
    # We will simulate cme writing a new file and a confluence-lock.json when we call download
    def mock_subprocess_run(cmd, env, **kwargs):
        new_file = tmp_path / "Jenkins" / "CI_CD.md"
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_text("# CI/CD\n", encoding="utf-8")
        
        lock_data = {
            "lockfile_version": 2,
            "orgs": {
                "https://km.fubonlife.com.tw/confluence": {
                    "spaces": {
                        "VL70J": {
                            "pages": {
                                "1145440219": {
                                    "title": "CI/CD 流程導入",
                                    "export_path": "Jenkins\\CI_CD.md"
                                }
                            }
                        }
                    }
                }
            }
        }
        
        lockfile = tmp_path / "confluence-lock.json"
        with open(lockfile, "w", encoding="utf-8") as f:
            json.dump(lock_data, f)
            
        return MagicMock(returncode=0, stdout="Done", stderr="")
        
    tracker = FileTracker()
    svc = DownloadService(cfg, tracker)
    
    with patch("services.download_service.subprocess.run", side_effect=mock_subprocess_run):
        ok, msg = svc.download(
            page_url="https://km.fubonlife.com.tw/confluence/spaces/VL70J/pages/1145440211/Jenkins",
            scope=DownloadScope.RECURSIVE,
            target_dir=tmp_path,
            write_frontmatter=True,
        )
        
    assert ok is True
    
    # Check that the frontmatter contains the exact values from confluence-lock.json
    new_fm = tracker.read_frontmatter(tmp_path / "Jenkins" / "CI_CD.md")
    assert new_fm.get("confluence_id") == "1145440219"
    assert new_fm.get("confluence_space") == "VL70J"
    assert new_fm.get("confluence_page_name") == "CI/CD 流程導入"
    assert new_fm.get("confluence_url") == "https://km.fubonlife.com.tw/confluence/spaces/VL70J/pages/1145440219"


