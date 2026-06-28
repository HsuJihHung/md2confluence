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
            callback(str(path), f"Uploading {path.name}...")

        cmd = self._build_cmd(path)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if callback:
                callback(str(path), f"x {msg}")
            return path, False, msg

        page_info = self._parse_page_info(result.stdout, path)
        if page_info:
            self.tracker.write_sync_state(path, page_info)

        if callback:
            callback(str(path), f"Uploaded {path.name}")
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
