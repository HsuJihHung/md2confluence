import logging
import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Callable

from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker

_log = logging.getLogger(__name__)


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
            progress_callback(f"Downloading {page_url}...")

        env = {**os.environ, **self.config.as_env_dict()}
        cmd = self._build_cmd(page_url, scope, target_dir)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if progress_callback:
                progress_callback(f"x {msg}")
            return False, msg

        if write_frontmatter:
            self._write_frontmatter_for_new_files(target_dir, page_url)

        if progress_callback:
            progress_callback("✓ Download complete")
        return True, result.stdout

    def _build_cmd(self, url: str, scope: DownloadScope, target_dir: Path) -> list[str]:
        exe = shutil.which("cme")
        base = [exe] if exe else [sys.executable, "-m", "cme"]
        subcommand = "pages" if scope == DownloadScope.SINGLE else "pages-with-descendants"
        return base + [subcommand, url, "--output-dir", str(target_dir)]

    def _write_frontmatter_for_new_files(self, target_dir: Path, source_url: str) -> None:
        # cme may write confluence_id into frontmatter during export.
        # For files where it doesn't, we write confluence_url only.
        # Those files will appear as NOT_LINKED in scan() until the
        # user assigns a confluence_id via "Change ID…".
        for path in target_dir.rglob("*.md"):
            fm = self.tracker.read_frontmatter(path)
            if not fm.get("confluence_id"):
                try:
                    self.tracker.write_sync_state(path, {"confluence_url": source_url})
                except Exception as exc:
                    _log.warning("Failed to write frontmatter for %s: %s", path, exc)
