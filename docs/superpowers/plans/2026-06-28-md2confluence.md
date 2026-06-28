# md2confluence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a NiceGUI local web app for bidirectional Confluence ↔ Markdown sync, distributed as a PyInstaller executable.

**Architecture:** Three-layer architecture — NiceGUI UI calls service layer (UploadService, DownloadService, FileTracker, ConfluenceConfig), which wraps `markdown-to-confluence` and `confluence-markdown-exporter` CLI tools via subprocess. File-to-Confluence mapping stored as YAML frontmatter in each `.md` file (body-only hash for dirty detection).

**Tech Stack:** Python 3.10+, NiceGUI ≥1.4, markdown-to-confluence, confluence-markdown-exporter, python-frontmatter, PyInstaller, pytest

---

## File Map

```
md2confluence/
├── app.py                        # Entry point — NiceGUI server
├── ui/
│   ├── __init__.py
│   ├── main_layout.py            # Split-panel shell, toolbar, status bar
│   ├── file_panel.py             # Left panel: flat list + tree toggle
│   ├── detail_panel.py           # Right panel: info card, actions, log
│   ├── download_dialog.py        # Download page dialog
│   └── config_page.py            # Config page (4 sections)
├── services/
│   ├── __init__.py
│   ├── confluence_config.py      # Settings model + load/save
│   ├── file_tracker.py           # Scan dir, read/write frontmatter, hash
│   ├── upload_service.py         # MD → Confluence via md2conf
│   └── download_service.py       # Confluence → MD via cme
├── tests/
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       ├── test_confluence_config.py
│       ├── test_file_tracker.py
│       ├── test_upload_service.py
│       └── test_download_service.py
├── build/
│   └── md2confluence.spec
└── requirements.txt
```

---

### Task 1: Project Setup

**Files:** `requirements.txt`, `app.py`, all `__init__.py` stubs

- [ ] **Step 1: Create directories**

```bash
mkdir -p ui services tests/services build docs/superpowers/plans
```

- [ ] **Step 2: Create `requirements.txt`**

```
nicegui>=1.4.0
markdown-to-confluence>=1.0.0
confluence-markdown-exporter>=5.0.0
python-frontmatter>=1.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: Install**

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: Create empty `__init__.py` files**

Create empty files at: `ui/__init__.py`, `services/__init__.py`, `tests/__init__.py`, `tests/services/__init__.py`

- [ ] **Step 5: Create `app.py` stub**

```python
from nicegui import ui

def main():
    ui.label("md2confluence — starting up")
    ui.run(title="md2confluence", port=0, reload=False)

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify NiceGUI starts**

```bash
python app.py
```

Expected: browser opens, shows "md2confluence — starting up". Press Ctrl+C to stop.

- [ ] **Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold"
```

---

### Task 2: ConfluenceConfig — Settings Model

**Files:**
- Create: `services/confluence_config.py`
- Create: `tests/services/test_confluence_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_confluence_config.py
from pathlib import Path
from services.confluence_config import ConfluenceConfig, DeploymentType


def test_default_is_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    assert cfg.deployment == DeploymentType.CLOUD


def test_save_and_load_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "user@co.com"
    cfg.cloud_api_token = "secret"
    cfg.default_space = "TEAM"
    cfg.save()

    cfg2 = ConfluenceConfig(config_dir=tmp_path)
    assert cfg2.cloud_domain == "co.atlassian.net"
    assert cfg2.cloud_email == "user@co.com"
    assert cfg2.cloud_api_token == "secret"
    assert cfg2.default_space == "TEAM"


def test_save_and_load_server(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_url = "https://confluence.co.com"
    cfg.server_context_path = "/wiki"
    cfg.server_username = "jsmith"
    cfg.server_password = "pass"
    cfg.save()

    cfg2 = ConfluenceConfig(config_dir=tmp_path)
    assert cfg2.deployment == DeploymentType.SERVER
    assert cfg2.server_url == "https://confluence.co.com"
    assert cfg2.server_context_path == "/wiki"


def test_as_env_dict_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "user@co.com"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "TEAM"
    env = cfg.as_env_dict()
    assert env["CONFLUENCE_DOMAIN"] == "co.atlassian.net"
    assert env["CONFLUENCE_USER_NAME"] == "user@co.com"
    assert env["CONFLUENCE_API_KEY"] == "tok"
    assert env["CONFLUENCE_SPACE_KEY"] == "TEAM"


def test_as_env_dict_server(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_url = "https://confluence.co.com"
    cfg.server_context_path = "/wiki"
    cfg.server_username = "jsmith"
    cfg.server_password = "pass"
    cfg.default_space = "DEV"
    env = cfg.as_env_dict()
    assert env["CONFLUENCE_DOMAIN"] == "confluence.co.com"
    assert env["CONFLUENCE_PATH"] == "/wiki"
    assert env["CONFLUENCE_USER_NAME"] == "jsmith"
    assert env["CONFLUENCE_API_KEY"] == "pass"
    assert env["CONFLUENCE_SPACE_KEY"] == "DEV"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/services/test_confluence_config.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `services/confluence_config.py`**

```python
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class DeploymentType(str, Enum):
    CLOUD = "cloud"
    SERVER = "server"


@dataclass
class ConfluenceConfig:
    config_dir: Path = field(default_factory=lambda: Path.home() / ".md2confluence")

    deployment: DeploymentType = DeploymentType.CLOUD

    cloud_domain: str = ""
    cloud_email: str = ""
    cloud_api_token: str = ""

    server_url: str = ""
    server_context_path: str = ""
    server_username: str = ""
    server_password: str = ""
    server_pat: str = ""

    default_space: str = ""

    mermaid_mode: str = "local"       # "local" | "macro"
    plantuml_mode: str = "remote"     # "remote" | "local"
    plantuml_server: str = "https://www.plantuml.com/plantuml"

    default_parent_page_id: str = ""
    skip_title_heading: bool = True
    auto_upload_images: bool = True

    theme: str = "dark"               # "dark" | "light"
    default_view: str = "flat"        # "flat" | "tree"
    last_directory: str = ""

    def __post_init__(self):
        self.config_dir = Path(self.config_dir)
        self._settings_file = self.config_dir / "settings.json"
        self._load()

    def _load(self):
        if not self._settings_file.exists():
            return
        data = json.loads(self._settings_file.read_text(encoding="utf-8"))
        for key, value in data.items():
            if key == "deployment":
                value = DeploymentType(value)
            if hasattr(self, key) and key != "config_dir":
                setattr(self, key, value)

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if k != "config_dir"}
        self._settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def as_env_dict(self) -> dict[str, str]:
        if self.deployment == DeploymentType.CLOUD:
            return {
                "CONFLUENCE_DOMAIN": self.cloud_domain,
                "CONFLUENCE_PATH": "",
                "CONFLUENCE_USER_NAME": self.cloud_email,
                "CONFLUENCE_API_KEY": self.cloud_api_token,
                "CONFLUENCE_SPACE_KEY": self.default_space,
            }
        parsed = urlparse(self.server_url)
        domain = parsed.netloc or self.server_url
        password = self.server_pat or self.server_password
        return {
            "CONFLUENCE_DOMAIN": domain,
            "CONFLUENCE_PATH": self.server_context_path,
            "CONFLUENCE_USER_NAME": self.server_username,
            "CONFLUENCE_API_KEY": password,
            "CONFLUENCE_SPACE_KEY": self.default_space,
        }
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/services/test_confluence_config.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/confluence_config.py tests/services/test_confluence_config.py
git commit -m "feat: ConfluenceConfig with load/save and env dict"
```

---

### Task 3: FileTracker — Frontmatter & Hash

**Files:**
- Create: `services/file_tracker.py`
- Create: `tests/services/test_file_tracker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_file_tracker.py
from pathlib import Path
from services.file_tracker import FileTracker, FileInfo, SyncStatus


def _write_md(path: Path, body: str, fm: dict = None):
    lines = ["---"]
    for k, v in (fm or {}).items():
        lines.append(f'{k}: "{v}"')
    lines += ["---", body]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_scan_finds_only_md_files(tmp_path):
    (tmp_path / "a.md").write_text("# Hello", encoding="utf-8")
    (tmp_path / "b.txt").write_text("ignored", encoding="utf-8")
    results = FileTracker().scan(tmp_path)
    assert len(results) == 1
    assert results[0].path.name == "a.md"


def test_scan_is_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    (sub / "b.md").write_text("# B", encoding="utf-8")
    assert len(FileTracker().scan(tmp_path)) == 2


def test_not_linked_when_no_frontmatter(tmp_path):
    (tmp_path / "a.md").write_text("# Hello", encoding="utf-8")
    result = FileTracker().scan(tmp_path)[0]
    assert result.status == SyncStatus.NOT_LINKED


def test_synced_when_hash_matches(tmp_path):
    path = tmp_path / "a.md"
    body = "# Hello"
    tracker = FileTracker()
    h = tracker.compute_body_hash_from_text(body)
    _write_md(path, body, {"confluence_id": "123", "confluence_content_hash": f"sha256:{h}"})
    assert tracker.scan(tmp_path)[0].status == SyncStatus.SYNCED


def test_modified_locally_when_hash_differs(tmp_path):
    path = tmp_path / "a.md"
    _write_md(path, "# Hello", {"confluence_id": "123", "confluence_content_hash": "sha256:stale"})
    assert FileTracker().scan(tmp_path)[0].status == SyncStatus.MODIFIED_LOCALLY


def test_write_sync_state_adds_frontmatter(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello world", encoding="utf-8")
    tracker = FileTracker()
    tracker.write_sync_state(path, {
        "confluence_id": "456",
        "confluence_space": "TEAM",
        "confluence_page_name": "Hello",
        "confluence_url": "https://example.com/pages/456",
    })
    fm = tracker.read_frontmatter(path)
    assert fm["confluence_id"] == "456"
    assert "confluence_last_sync" in fm
    assert fm["confluence_content_hash"].startswith("sha256:")


def test_body_hash_excludes_frontmatter(tmp_path):
    path = tmp_path / "a.md"
    body = "# Hello world"
    _write_md(path, body, {"confluence_id": "123"})
    tracker = FileTracker()
    assert tracker.compute_body_hash(path) == tracker.compute_body_hash_from_text(body)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/services/test_file_tracker.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `services/file_tracker.py`**

```python
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import frontmatter as fm_lib


class SyncStatus(str, Enum):
    SYNCED = "synced"
    MODIFIED_LOCALLY = "modified_locally"
    NOT_LINKED = "not_linked"
    FAILED = "failed"


@dataclass
class FileInfo:
    path: Path
    status: SyncStatus
    confluence_id: str = ""
    confluence_space: str = ""
    confluence_page_name: str = ""
    confluence_url: str = ""
    confluence_last_sync: str = ""


class FileTracker:
    def scan(self, directory: Path) -> list[FileInfo]:
        return [self._inspect(p) for p in sorted(directory.rglob("*.md"))]

    def _inspect(self, path: Path) -> FileInfo:
        fm = self.read_frontmatter(path)
        cid = str(fm.get("confluence_id", "")).strip()
        if not cid:
            return FileInfo(path=path, status=SyncStatus.NOT_LINKED)

        stored = str(fm.get("confluence_content_hash", ""))
        current = f"sha256:{self.compute_body_hash(path)}"
        status = SyncStatus.SYNCED if current == stored else SyncStatus.MODIFIED_LOCALLY

        return FileInfo(
            path=path,
            status=status,
            confluence_id=cid,
            confluence_space=fm.get("confluence_space", ""),
            confluence_page_name=fm.get("confluence_page_name", ""),
            confluence_url=fm.get("confluence_url", ""),
            confluence_last_sync=fm.get("confluence_last_sync", ""),
        )

    def read_frontmatter(self, path: Path) -> dict[str, Any]:
        try:
            return dict(fm_lib.load(str(path)).metadata)
        except Exception:
            return {}

    def write_sync_state(self, path: Path, page_info: dict[str, str]) -> None:
        try:
            post = fm_lib.load(str(path))
        except Exception:
            post = fm_lib.Post(path.read_text(encoding="utf-8"))
        post.metadata.update({
            **page_info,
            "confluence_last_sync": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "confluence_content_hash": f"sha256:{self.compute_body_hash(path)}",
        })
        path.write_text(fm_lib.dumps(post), encoding="utf-8")

    def compute_body_hash(self, path: Path) -> str:
        try:
            body = fm_lib.load(str(path)).content
        except Exception:
            body = path.read_text(encoding="utf-8")
        return self.compute_body_hash_from_text(body)

    def compute_body_hash_from_text(self, body: str) -> str:
        return hashlib.sha256(body.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/services/test_file_tracker.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/file_tracker.py tests/services/test_file_tracker.py
git commit -m "feat: FileTracker with frontmatter and body-only hash"
```

---

### Task 4: UploadService

**Files:**
- Create: `services/upload_service.py`
- Create: `tests/services/test_upload_service.py`

**Note on CLI invocation:** `markdown-to-confluence` installs as `md2conf`. In tests, subprocess is mocked. In production, the service calls `shutil.which("md2conf")` and falls back to `[sys.executable, "-m", "md2conf"]` if the script isn't found in PATH (e.g. inside a PyInstaller bundle that doesn't add scripts to PATH). After first run, check `md2conf --help` to confirm exact flag names for `--skip-title-heading` and `--no-render-mermaid`.

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_upload_service.py
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

    tracker.write_sync_state.assert_called_once()


def test_progress_callback_called(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    cfg = _make_cfg(tmp_path)
    calls = []

    with patch("services.upload_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        UploadService(cfg, MagicMock()).upload([path], progress_callback=lambda f, m: calls.append(m))

    assert len(calls) >= 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/services/test_upload_service.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `services/upload_service.py`**

```python
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker


class UploadService:
    def __init__(self, config: ConfluenceConfig, tracker: FileTracker | None = None):
        self.config = config
        self.tracker = tracker or FileTracker()

    def upload(
        self,
        paths: list[Path],
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, bool, str]]:
        env = {**os.environ, **self.config.as_env_dict()}
        return [self._upload_one(p, env, progress_callback) for p in paths]

    def _upload_one(
        self,
        path: Path,
        env: dict,
        callback: Callable | None,
    ) -> tuple[Path, bool, str]:
        if callback:
            callback(str(path), f"Uploading {path.name}…")

        cmd = self._build_cmd(path)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if callback:
                callback(str(path), f"✗ {msg}")
            return path, False, msg

        page_info = self._parse_page_info(result.stdout, path)
        if page_info:
            self.tracker.write_sync_state(path, page_info)

        if callback:
            callback(str(path), f"✓ Uploaded {path.name}")
        return path, True, result.stdout

    def _build_cmd(self, path: Path) -> list[str]:
        exe = shutil.which("md2conf") or None
        base = [exe] if exe else [sys.executable, "-m", "md2conf"]
        cmd = base + [str(path)]
        if self.config.skip_title_heading:
            cmd.append("--skip-title-heading")
        if self.config.mermaid_mode == "local":
            cmd.append("--render-mermaid")
        return cmd

    def _parse_page_info(self, stdout: str, path: Path) -> dict | None:
        # md2conf prints "Page ID: <id>" on success.
        # Adjust this parser if the actual output format differs.
        for line in stdout.splitlines():
            if "Page ID:" in line:
                page_id = line.split("Page ID:", 1)[-1].strip()
                return {
                    "confluence_id": page_id,
                    "confluence_space": self.config.default_space,
                }
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/services/test_upload_service.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/upload_service.py tests/services/test_upload_service.py
git commit -m "feat: UploadService wrapping md2conf CLI"
```

---

### Task 5: DownloadService

**Files:**
- Create: `services/download_service.py`
- Create: `tests/services/test_download_service.py`

**Note:** `confluence-markdown-exporter` CLI is `cme`. Commands: `cme pages <url>` (single), `cme pages-with-descendants <url>` (recursive). Check `cme --help` after install to confirm the `--output` / `--output-dir` flag name for specifying the target directory.

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_download_service.py
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/services/test_download_service.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `services/download_service.py`**

```python
import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Callable

from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker


class DownloadScope(str, Enum):
    SINGLE = "single"
    RECURSIVE = "recursive"


class DownloadService:
    def __init__(self, config: ConfluenceConfig, tracker: FileTracker | None = None):
        self.config = config
        self.tracker = tracker or FileTracker()

    def download(
        self,
        page_url: str,
        scope: DownloadScope,
        target_dir: Path,
        overwrite: bool = False,
        download_attachments: bool = True,
        write_frontmatter: bool = True,
        progress_callback: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        if progress_callback:
            progress_callback(f"Downloading {page_url}…")

        env = {**os.environ, **self.config.as_env_dict()}
        cmd = self._build_cmd(page_url, scope, target_dir)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if progress_callback:
                progress_callback(f"✗ {msg}")
            return False, msg

        if write_frontmatter:
            self._write_frontmatter_for_new_files(target_dir, page_url)

        if progress_callback:
            progress_callback("✓ Download complete")
        return True, result.stdout

    def _build_cmd(self, url: str, scope: DownloadScope, target_dir: Path) -> list[str]:
        exe = shutil.which("cme") or None
        base = [exe] if exe else [sys.executable, "-m", "cme"]
        subcommand = "pages" if scope == DownloadScope.SINGLE else "pages-with-descendants"
        # --output-dir flag: verify exact name with `cme --help`
        return base + [subcommand, url, "--output-dir", str(target_dir)]

    def _write_frontmatter_for_new_files(self, target_dir: Path, source_url: str) -> None:
        # After download, write confluence_url to frontmatter of any .md files
        # that were just created (identified by missing confluence_id frontmatter).
        for path in target_dir.rglob("*.md"):
            fm = self.tracker.read_frontmatter(path)
            if not fm.get("confluence_id"):
                self.tracker.write_sync_state(path, {"confluence_url": source_url})
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/services/test_download_service.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Run all service tests**

```bash
pytest tests/ -v
```

Expected: All 20 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/download_service.py tests/services/test_download_service.py
git commit -m "feat: DownloadService wrapping cme CLI"
```

---

### Task 6: App Shell & Main Layout

**Files:**
- Modify: `app.py`
- Create: `ui/main_layout.py`

NiceGUI key APIs used here:
- `ui.header()` — top toolbar
- `ui.splitter()` — left/right split panel
- `ui.footer()` — status bar
- `ui.navigate.to("/config")` — routing
- `@ui.page("/")` — page decorator

- [ ] **Step 1: Create `ui/main_layout.py`**

```python
# ui/main_layout.py
from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker, FileInfo


class MainLayout:
    def __init__(self, config: ConfluenceConfig, tracker: FileTracker):
        self.config = config
        self.tracker = tracker
        self.selected_file: FileInfo | None = None
        self.files: list[FileInfo] = []
        self._log_label = None
        self._detail_container = None
        self._file_list_container = None
        self._status_label = None

    def build(self):
        with ui.header().classes("items-center gap-2 px-4 py-2 bg-gray-900"):
            ui.label("md2confluence").classes("text-indigo-400 font-bold text-sm")
            self._dir_input = ui.input(
                placeholder="Select directory…",
                value=self.config.last_directory,
            ).classes("flex-1 max-w-xs text-xs")
            ui.button("Browse…", on_click=self._browse).classes("text-xs")
            ui.button("⟳ Refresh", on_click=self._refresh).classes("text-xs").tooltip(
                "Rescan directory and recompute sync status (no API calls)"
            )
            ui.space()
            ui.button("⬇ Download Page…", on_click=self._open_download_dialog).classes("text-xs")
            ui.button("⚙ Config", on_click=lambda: ui.navigate.to("/config")).classes("text-xs")

        with ui.splitter(value=28).classes("w-full flex-1") as splitter:
            with splitter.before:
                self._file_list_container = ui.column().classes("w-full h-full")
                self._build_file_panel()
            with splitter.after:
                self._detail_container = ui.column().classes("w-full h-full p-4")
                self._build_detail_panel()

        with ui.footer().classes("px-4 py-1 bg-gray-950 text-xs text-gray-500 flex gap-4"):
            self._conn_dot = ui.label("● Connected").classes("text-green-400")
            ui.label(self.config.cloud_domain or self.config.server_url)
            ui.space()
            self._status_label = ui.label("No directory loaded")

    # Stubs — filled in Tasks 8, 9, 10
    def _build_file_panel(self): pass
    def _build_detail_panel(self): pass
    def _open_download_dialog(self): pass

    def _browse(self):
        # NiceGUI file picker opens a directory chooser dialog
        async def _pick():
            result = await ui.run_javascript(
                'window.__dir = prompt("Enter directory path:"); window.__dir;'
            )
            if result:
                self._dir_input.value = result
                self.config.last_directory = result
                self.config.save()
                self._refresh()
        import asyncio
        asyncio.ensure_future(_pick())

    def _refresh(self):
        directory = self._dir_input.value.strip()
        if not directory:
            return
        from pathlib import Path
        self.files = self.tracker.scan(Path(directory))
        counts = {s: 0 for s in ["synced", "modified_locally", "not_linked", "failed"]}
        for f in self.files:
            counts[f.status.value] = counts.get(f.status.value, 0) + 1
        if self._status_label:
            self._status_label.set_text(
                f"{counts['synced']} synced · {counts['modified_locally']} modified · "
                f"{counts['not_linked']} unlinked · {counts['failed']} error"
            )
        self._rebuild_file_list()

    def _rebuild_file_list(self):
        if self._file_list_container:
            self._file_list_container.clear()
            with self._file_list_container:
                self._build_file_panel()
```

- [ ] **Step 2: Update `app.py`**

```python
from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker
from ui.main_layout import MainLayout


config = ConfluenceConfig()
tracker = FileTracker()


@ui.page("/")
def index():
    layout = MainLayout(config, tracker)
    layout.build()


def main():
    ui.run(title="md2confluence", port=0, reload=False, dark=config.theme == "dark")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify app starts without error**

```bash
python app.py
```

Expected: browser opens showing header toolbar and split panel shell (detail area is empty — that's fine at this stage). No Python errors in terminal.

- [ ] **Step 4: Commit**

```bash
git add app.py ui/main_layout.py
git commit -m "feat: app shell with split-panel layout and toolbar"
```

---

### Task 7: Config Page UI

**Files:**
- Create: `ui/config_page.py`
- Modify: `app.py` (register `/config` route)

- [ ] **Step 1: Create `ui/config_page.py`**

```python
# ui/config_page.py
from nicegui import ui
from services.confluence_config import ConfluenceConfig, DeploymentType


def build_config_page(config: ConfluenceConfig):
    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
        ui.label("Configuration").classes("text-xl font-bold text-indigo-400")

        # --- Connection ---
        with ui.card().classes("w-full"):
            ui.label("🔌 Confluence Connection").classes("font-bold text-indigo-300 mb-2")

            deployment_toggle = ui.toggle(
                {DeploymentType.CLOUD: "☁ Cloud", DeploymentType.SERVER: "🏢 Server / DC"},
                value=config.deployment,
            )

            cloud_section = ui.column().classes("w-full gap-2")
            server_section = ui.column().classes("w-full gap-2")

            with cloud_section:
                ui.label("Cloud Settings").classes("text-xs text-gray-400 uppercase mt-2")
                cloud_domain = ui.input("Domain", value=config.cloud_domain,
                                        placeholder="yourcompany.atlassian.net").classes("w-full")
                cloud_email = ui.input("Email", value=config.cloud_email).classes("w-full")
                cloud_token = ui.input("API Token", value=config.cloud_api_token,
                                       password=True, password_toggle_button=True).classes("w-full")

            with server_section:
                ui.label("Server Settings").classes("text-xs text-gray-400 uppercase mt-2")
                server_url = ui.input("Server URL", value=config.server_url,
                                      placeholder="https://confluence.yourcompany.com").classes("w-full")
                server_path = ui.input("Context Path", value=config.server_context_path,
                                       placeholder="/confluence").classes("w-full")
                server_user = ui.input("Username", value=config.server_username).classes("w-full")
                server_pass = ui.input("Password", value=config.server_password,
                                       password=True, password_toggle_button=True).classes("w-full")

            default_space = ui.input("Default Space Key", value=config.default_space,
                                     placeholder="TEAM").classes("w-full mt-2")

            def _update_visibility():
                is_cloud = deployment_toggle.value == DeploymentType.CLOUD
                cloud_section.set_visibility(is_cloud)
                server_section.set_visibility(not is_cloud)

            deployment_toggle.on_value_change(lambda _: _update_visibility())
            _update_visibility()

            conn_status = ui.label("").classes("text-xs mt-2")

            def _test_connection():
                conn_status.set_text("Testing…")
                conn_status.classes(replace="text-xs mt-2 text-yellow-400")
                # Lightweight test: just validate fields are non-empty
                domain = cloud_domain.value if deployment_toggle.value == DeploymentType.CLOUD else server_url.value
                if domain:
                    conn_status.set_text("✓ Fields look valid — test by uploading a file")
                    conn_status.classes(replace="text-xs mt-2 text-green-400")
                else:
                    conn_status.set_text("✗ Domain/URL is required")
                    conn_status.classes(replace="text-xs mt-2 text-red-400")

            ui.button("⚡ Test Connection", on_click=_test_connection).classes("mt-2")

        # --- Diagram Rendering ---
        with ui.card().classes("w-full"):
            ui.label("📊 Diagram Rendering").classes("font-bold text-indigo-300 mb-2")
            mermaid_toggle = ui.toggle(
                {"local": "Render locally (mmdc)", "macro": "Confluence macro"},
                value=config.mermaid_mode,
            )
            ui.label("Local rendering requires @mermaid-js/mermaid-cli (npm)").classes("text-xs text-gray-500")
            plantuml_toggle = ui.toggle(
                {"remote": "Remote server", "local": "Local jar"},
                value=config.plantuml_mode,
            ).classes("mt-2")
            plantuml_server = ui.input("PlantUML Server URL", value=config.plantuml_server).classes("w-full mt-1")

        # --- Upload Defaults ---
        with ui.card().classes("w-full"):
            ui.label("⬆ Upload Defaults").classes("font-bold text-indigo-300 mb-2")
            parent_page = ui.input("Default Parent Page ID (optional)",
                                   value=config.default_parent_page_id).classes("w-full")
            skip_title = ui.checkbox("Remove H1 that duplicates page title",
                                     value=config.skip_title_heading)
            auto_images = ui.checkbox("Auto-upload local images as attachments",
                                      value=config.auto_upload_images)

        # --- App Preferences ---
        with ui.card().classes("w-full"):
            ui.label("🎨 App Preferences").classes("font-bold text-indigo-300 mb-2")
            theme_toggle = ui.toggle({"dark": "🌙 Dark", "light": "☀ Light"}, value=config.theme)
            view_toggle = ui.toggle({"flat": "≡ Flat", "tree": "⊞ Tree"},
                                    value=config.default_view).classes("mt-2")

        # --- Save ---
        def _save():
            config.deployment = deployment_toggle.value
            config.cloud_domain = cloud_domain.value
            config.cloud_email = cloud_email.value
            config.cloud_api_token = cloud_token.value
            config.server_url = server_url.value
            config.server_context_path = server_path.value
            config.server_username = server_user.value
            config.server_password = server_pass.value
            config.default_space = default_space.value
            config.mermaid_mode = mermaid_toggle.value
            config.plantuml_mode = plantuml_toggle.value
            config.plantuml_server = plantuml_server.value
            config.default_parent_page_id = parent_page.value
            config.skip_title_heading = skip_title.value
            config.auto_upload_images = auto_images.value
            config.theme = theme_toggle.value
            config.default_view = view_toggle.value
            config.save()
            ui.notify("Settings saved", type="positive")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=lambda: ui.navigate.to("/")).classes("text-gray-400")
            ui.button("Save Settings", on_click=_save).classes("bg-indigo-600 text-white")
```

- [ ] **Step 2: Register the config route in `app.py`**

```python
# Add after the index() function in app.py:
from ui.config_page import build_config_page

@ui.page("/config")
def config_page():
    build_config_page(config)
```

- [ ] **Step 3: Verify config page**

```bash
python app.py
```

Navigate to `http://localhost:<port>/config`. Verify: Cloud/Server toggle switches field sections; Save shows a toast notification.

- [ ] **Step 4: Commit**

```bash
git add ui/config_page.py app.py
git commit -m "feat: config page UI with all four sections"
```

---

### Task 8: File Panel — Flat List & Tree View

**Files:**
- Modify: `ui/main_layout.py` (fill in `_build_file_panel`)

- [ ] **Step 1: Replace the `_build_file_panel` stub in `ui/main_layout.py`**

```python
def _build_file_panel(self):
    with self._file_list_container:
        # View toggle bar
        with ui.row().classes("w-full items-center px-2 py-1 bg-gray-900 border-b border-gray-800 gap-1"):
            ui.label("View:").classes("text-xs text-gray-500")
            self._view_btn_flat = ui.button(
                "≡ Flat", on_click=lambda: self._set_view("flat")
            ).classes("text-xs px-2 py-0.5")
            self._view_btn_tree = ui.button(
                "⊞ Tree", on_click=lambda: self._set_view("tree")
            ).classes("text-xs px-2 py-0.5")
            ui.space()
            self._file_count_label = ui.label(f"{len(self.files)} files").classes("text-xs text-gray-500")

        self._flat_container = ui.column().classes("w-full overflow-y-auto")
        self._tree_container = ui.column().classes("w-full overflow-y-auto")

        self._render_flat_list()
        self._render_tree_list()
        self._set_view(self.config.default_view)

def _set_view(self, view: str):
    self._flat_container.set_visibility(view == "flat")
    self._tree_container.set_visibility(view == "tree")

def _render_flat_list(self):
    self._flat_container.clear()
    with self._flat_container:
        for info in self.files:
            self._file_row(info, indent=0)

def _render_tree_list(self):
    from pathlib import Path
    self._tree_container.clear()
    # Group files by parent directory relative to the base directory
    base = Path(self.config.last_directory) if self.config.last_directory else None
    dirs: dict[Path, list] = {}
    for info in self.files:
        parent = info.path.parent
        dirs.setdefault(parent, []).append(info)

    with self._tree_container:
        for parent, infos in sorted(dirs.items()):
            rel = parent.relative_to(base) if base else parent
            with ui.row().classes("items-center px-2 py-1 gap-1"):
                ui.label("▾").classes("text-gray-500 text-xs")
                ui.label(str(rel) + "/").classes("text-xs text-gray-400 uppercase")
            for info in infos:
                self._file_row(info, indent=16)

def _file_row(self, info, indent: int = 0):
    dot_color = {
        "synced": "bg-green-500",
        "modified_locally": "bg-orange-400",
        "not_linked": "bg-gray-500",
        "failed": "bg-red-500",
    }.get(info.status.value, "bg-gray-500")

    is_selected = self.selected_file and self.selected_file.path == info.path
    row_classes = (
        f"w-full flex flex-col px-3 py-2 cursor-pointer border-b border-gray-800 "
        f"{'bg-indigo-950' if is_selected else 'hover:bg-gray-800'}"
    )

    with ui.element("div").classes(row_classes).style(f"padding-left:{indent + 12}px").on(
        "click", lambda _, i=info: self._select_file(i)
    ):
        with ui.row().classes("items-center gap-1.5"):
            ui.element("span").classes(f"w-2 h-2 rounded-full flex-shrink-0 {dot_color}")
            ui.label(info.path.name).classes(
                f"text-xs {'font-bold text-white' if is_selected else 'text-gray-300'}"
            )
        sub = ""
        if info.confluence_id:
            sub = f"ID: {info.confluence_id} · {info.confluence_last_sync[:10] if info.confluence_last_sync else ''}"
        elif info.status.value == "failed":
            sub = "last operation failed"
        else:
            sub = "not linked"
        ui.label(sub).classes("text-xs text-gray-600 ml-3.5")

def _select_file(self, info):
    self.selected_file = info
    self._rebuild_file_list()
    self._rebuild_detail()
```

- [ ] **Step 2: Add `_rebuild_detail` stub to `MainLayout.__init__` area**

```python
def _rebuild_detail(self):
    if self._detail_container:
        self._detail_container.clear()
        with self._detail_container:
            self._build_detail_panel()
```

- [ ] **Step 3: Verify file panel**

```bash
python app.py
```

Enter a directory with some `.md` files in Browse, click Refresh. Verify: files appear with color dots; clicking switches selection highlight; Flat/Tree toggle works.

- [ ] **Step 4: Commit**

```bash
git add ui/main_layout.py
git commit -m "feat: file panel with flat list, tree view, and file selection"
```

---

### Task 9: Detail Panel

**Files:**
- Modify: `ui/main_layout.py` (fill in `_build_detail_panel`)

- [ ] **Step 1: Replace the `_build_detail_panel` stub in `ui/main_layout.py`**

```python
def _build_detail_panel(self):
    if not self.selected_file:
        with ui.column().classes("w-full h-full items-center justify-center"):
            ui.label("Select a file to view details").classes("text-gray-500 text-sm")
        return

    info = self.selected_file
    status_colors = {
        "synced": ("text-green-400", "bg-green-950"),
        "modified_locally": ("text-orange-400", "bg-orange-950"),
        "not_linked": ("text-gray-400", "bg-gray-800"),
        "failed": ("text-red-400", "bg-red-950"),
    }
    txt_color, badge_bg = status_colors.get(info.status.value, ("text-gray-400", "bg-gray-800"))

    with ui.column().classes("w-full gap-3"):
        # Header
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("gap-0.5"):
                ui.label(info.path.name).classes("text-white text-lg font-bold")
                ui.label(str(info.path)).classes("text-gray-500 text-xs")
            ui.label(f"● {info.status.value.replace('_', ' ')}").classes(
                f"text-xs px-3 py-1 rounded-full {txt_color} {badge_bg} whitespace-nowrap"
            )

        # Confluence info card
        with ui.card().classes("w-full bg-gray-900"):
            ui.label("Confluence").classes("text-xs text-gray-500 uppercase mb-2")
            if info.confluence_id:
                with ui.grid(columns=2).classes("w-full text-xs gap-y-1.5"):
                    ui.label("Page name").classes("text-gray-500")
                    ui.label(info.confluence_page_name or "—").classes("text-white font-bold")
                    ui.label("Path").classes("text-gray-500")
                    ui.label("—").classes("text-gray-300")  # breadcrumb — populated after API call
                    ui.label("Page ID").classes("text-gray-500")
                    ui.label(info.confluence_id).classes("text-indigo-400")
                    ui.label("Space").classes("text-gray-500")
                    ui.label(info.confluence_space or "—").classes("text-gray-300")
                    ui.label("Last sync").classes("text-gray-500")
                    ui.label(info.confluence_last_sync or "—").classes("text-gray-300")
                    ui.label("Open").classes("text-gray-500")
                    if info.confluence_url:
                        ui.link("View in Confluence ↗", target=info.confluence_url, new_tab=True).classes(
                            "text-indigo-400 text-xs"
                        )
                    else:
                        ui.label("—").classes("text-gray-500")
            else:
                ui.label("Not linked to a Confluence page yet.").classes("text-gray-500 text-xs")

        # Action buttons
        with ui.row().classes("gap-2 flex-wrap"):
            ui.button(
                "⬆ Upload to Confluence",
                on_click=lambda: self._do_upload([info.path]),
            ).classes("bg-indigo-600 text-white text-xs")
            ui.button(
                "⬇ Pull from Confluence",
                on_click=lambda: self._do_pull(info),
            ).props("outline").classes("text-xs")
            ui.button(
                "🔗 Change ID…",
                on_click=lambda: self._change_id_dialog(info),
            ).props("outline").classes("text-xs")

        # Log
        ui.label("Last Operation Log").classes("text-xs text-gray-500 uppercase")
        self._log_label = ui.log(max_lines=20).classes(
            "w-full h-32 bg-gray-950 text-xs font-mono rounded border border-gray-800"
        )

def _do_upload(self, paths):
    from services.upload_service import UploadService
    from pathlib import Path
    svc = UploadService(self.config, self.tracker)

    def _cb(file, msg):
        if self._log_label:
            self._log_label.push(msg)

    import asyncio

    async def _run():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: svc.upload(paths, progress_callback=_cb))
        self._refresh()

    asyncio.ensure_future(_run())

def _do_pull(self, info):
    if not info.confluence_url and not info.confluence_id:
        ui.notify("No Confluence URL linked to this file", type="warning")
        return
    from services.download_service import DownloadService, DownloadScope
    svc = DownloadService(self.config, self.tracker)

    def _cb(msg):
        if self._log_label:
            self._log_label.push(msg)

    import asyncio

    async def _run():
        url = info.confluence_url or info.confluence_id
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: svc.download(url, DownloadScope.SINGLE, info.path.parent,
                                  overwrite=True, progress_callback=_cb),
        )
        self._refresh()

    asyncio.ensure_future(_run())

def _change_id_dialog(self, info):
    with ui.dialog() as dlg, ui.card():
        ui.label("Set Confluence Page ID").classes("font-bold")
        new_id = ui.input("Page ID", placeholder="e.g. 98321").classes("w-full")

        def _apply():
            if new_id.value.strip():
                self.tracker.write_sync_state(info.path, {
                    "confluence_id": new_id.value.strip(),
                    "confluence_space": self.config.default_space,
                })
                dlg.close()
                self._refresh()
                ui.notify("Confluence ID updated", type="positive")

        with ui.row().classes("gap-2 justify-end w-full mt-2"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("Save", on_click=_apply).classes("bg-indigo-600 text-white")
    dlg.open()
```

- [ ] **Step 2: Verify detail panel**

```bash
python app.py
```

Select a file in the list. Verify: detail panel shows file name, status badge, Confluence info card (or "not linked" message), and the three action buttons.

- [ ] **Step 3: Commit**

```bash
git add ui/main_layout.py
git commit -m "feat: detail panel with Confluence info, actions, and log"
```

---

### Task 10: Download Dialog

**Files:**
- Create: `ui/download_dialog.py`
- Modify: `ui/main_layout.py` (fill in `_open_download_dialog`)

- [ ] **Step 1: Create `ui/download_dialog.py`**

```python
# ui/download_dialog.py
from pathlib import Path
from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.download_service import DownloadService, DownloadScope
from services.file_tracker import FileTracker


def open_download_dialog(config: ConfluenceConfig, tracker: FileTracker, default_dir: str = ""):
    with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg"):
        ui.label("⬇ Download from Confluence").classes("font-bold text-base mb-2")

        url_input = ui.input(
            "Confluence Page URL or Page ID",
            placeholder="https://company.atlassian.net/wiki/spaces/TEAM/pages/123  or  123",
        ).classes("w-full")
        resolved_label = ui.label("").classes("text-xs mt-0.5 text-gray-500")

        def _on_url_change():
            v = url_input.value.strip()
            if v:
                resolved_label.set_text("Enter a URL or page ID — page name will resolve on download")
            else:
                resolved_label.set_text("")

        url_input.on_value_change(lambda _: _on_url_change())

        ui.label("Scope").classes("text-xs text-gray-400 uppercase mt-3")
        scope_radio = ui.radio(
            {DownloadScope.SINGLE: "Single page", DownloadScope.RECURSIVE: "Page + all children (recursive)"},
            value=DownloadScope.SINGLE,
        ).classes("text-sm")

        ui.label("Save to").classes("text-xs text-gray-400 uppercase mt-3")
        with ui.row().classes("w-full gap-2"):
            dir_input = ui.input(value=default_dir).classes("flex-1")
            ui.button("Browse…", on_click=lambda: ui.notify("Enter path manually", type="info")).classes("text-xs")

        ui.label("Options").classes("text-xs text-gray-400 uppercase mt-3")
        opt_attachments = ui.checkbox("Download attachments and images", value=True)
        opt_frontmatter = ui.checkbox("Write Confluence ID to frontmatter", value=True)
        opt_overwrite = ui.checkbox("Overwrite existing files", value=False).tooltip(
            "When unchecked, files that already exist locally are skipped. "
            "When checked, existing files are replaced with the Confluence version."
        )

        progress_log = ui.log(max_lines=10).classes(
            "w-full h-24 bg-gray-950 text-xs font-mono rounded border border-gray-800 mt-3"
        )
        progress_log.set_visibility(False)

        def _download():
            url = url_input.value.strip()
            target = dir_input.value.strip()
            if not url or not target:
                ui.notify("URL and directory are required", type="warning")
                return

            progress_log.set_visibility(True)
            svc = DownloadService(config, tracker)

            def _cb(msg):
                progress_log.push(msg)

            import asyncio

            async def _run():
                loop = asyncio.get_event_loop()
                ok, msg = await loop.run_in_executor(
                    None,
                    lambda: svc.download(
                        page_url=url,
                        scope=scope_radio.value,
                        target_dir=Path(target),
                        overwrite=opt_overwrite.value,
                        download_attachments=opt_attachments.value,
                        write_frontmatter=opt_frontmatter.value,
                        progress_callback=_cb,
                    ),
                )
                if ok:
                    ui.notify("Download complete", type="positive")
                else:
                    ui.notify(f"Download failed: {msg}", type="negative")

            asyncio.ensure_future(_run())

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("⬇ Download", on_click=_download).classes("bg-indigo-600 text-white")

    dlg.open()
```

- [ ] **Step 2: Wire up `_open_download_dialog` in `ui/main_layout.py`**

```python
def _open_download_dialog(self):
    from ui.download_dialog import open_download_dialog
    open_download_dialog(self.config, self.tracker, default_dir=self.config.last_directory)
```

- [ ] **Step 3: Verify download dialog**

```bash
python app.py
```

Click "⬇ Download Page…" in toolbar. Verify: dialog opens with URL input, scope radio, directory field, options checkboxes, and Download button. Hover the "Overwrite existing files" checkbox to see the tooltip explaining what it does.

- [ ] **Step 4: Commit**

```bash
git add ui/download_dialog.py ui/main_layout.py
git commit -m "feat: download dialog with scope, options, and progress log"
```

---

### Task 11: Dark/Light Mode

**Files:**
- Modify: `app.py`
- Modify: `ui/config_page.py`

NiceGUI exposes `ui.dark_mode()` which returns a `DarkMode` element you can call `.enable()` / `.disable()` on, or bind to a value.

- [ ] **Step 1: Add dark mode support to `app.py`**

```python
# At the top of app.py, after imports, add:
from nicegui import ui, app as nicegui_app

# Replace the existing main() function with:
def main():
    dark = ui.dark_mode()

    @ui.page("/")
    def index():
        if config.theme == "dark":
            dark.enable()
        else:
            dark.disable()
        layout = MainLayout(config, tracker)
        layout.build()

    @ui.page("/config")
    def config_page_route():
        if config.theme == "dark":
            dark.enable()
        else:
            dark.disable()
        build_config_page(config)

    ui.run(title="md2confluence", port=0, reload=False)
```

- [ ] **Step 2: Apply theme on save in `ui/config_page.py`**

In the `_save` function inside `build_config_page`, after `config.save()`, add:

```python
# After config.save():
ui.notify("Settings saved — reload the page for theme change to take effect", type="positive")
```

- [ ] **Step 3: Verify dark/light toggle**

```bash
python app.py
```

Go to Config, switch to Light, save. Reload the page. Verify the background is light-colored.

- [ ] **Step 4: Commit**

```bash
git add app.py ui/config_page.py
git commit -m "feat: dark/light mode persisted via settings"
```

---

### Task 12: PyInstaller Build

**Files:**
- Create: `build/md2confluence.spec`

- [ ] **Step 1: Install PyInstaller**

```bash
pip install pyinstaller
```

- [ ] **Step 2: Create `build/md2confluence.spec`**

```python
# build/md2confluence.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect NiceGUI static files
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all("nicegui")

a = Analysis(
    ["../app.py"],
    pathex=[str(Path("..").resolve())],
    binaries=nicegui_binaries,
    datas=nicegui_datas,
    hiddenimports=nicegui_hiddenimports + [
        "services.confluence_config",
        "services.file_tracker",
        "services.upload_service",
        "services.download_service",
        "ui.main_layout",
        "ui.config_page",
        "ui.download_dialog",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="md2confluence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no terminal window
    icon=None,
)
```

- [ ] **Step 3: Build the executable**

```bash
cd build
pyinstaller md2confluence.spec
```

Expected: `build/dist/md2confluence.exe` created (takes ~2-3 minutes)

- [ ] **Step 4: Test the executable**

```bash
./dist/md2confluence.exe
```

Expected: browser opens at localhost with the app running. No console window appears.

- [ ] **Step 5: Verify CLI tools are bundled**

After the build succeeds, check that `md2conf` and `cme` are importable within the bundle by testing an upload from the running `.exe`. If they fail with "command not found", add them as hidden imports to the spec:

```python
# In hiddenimports, also add:
"md2conf",
"md2conf.__main__",
"confluence_markdown_exporter",
```

Then rebuild.

- [ ] **Step 6: Commit**

```bash
git add build/md2confluence.spec
git commit -m "chore: PyInstaller spec for standalone exe build"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered in |
|---|---|
| Standalone local web UI | Task 1, 6, 12 |
| Single file + directory upload | Task 4, 9 |
| Single page download | Task 5, 10 |
| Recursive page download | Task 5, 10 |
| Image / attachment handling | Task 4 (`auto_upload_images`), Task 5 (`download_attachments`) |
| File list with Confluence ID tracking | Task 3, 8 |
| Frontmatter tracking (confluence_id, hash) | Task 3 |
| Tables, Mermaid, PlantUML, code blocks | Config in Task 7; passed as flags in Task 4 |
| Config page (all env vars) | Task 7 |
| Dark / light mode | Task 11 |
| Tree view toggle | Task 8 |
| Download dialog with scope + overwrite | Task 10 |
| Pull from Confluence (per-file) | Task 9 |
| Change ID dialog | Task 9 |
| Status bar with counts | Task 6 |
| Both Cloud + Server/DC | Task 2, 7 |
| PyInstaller `.exe` | Task 12 |

No gaps found.
