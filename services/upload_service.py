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
        parent_page_id: str | None = None,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, bool, str]]:
        results = []
        for p in paths:
            file_env = {**os.environ, **self.config.as_env_dict()}
            info = self.tracker._inspect(p)
            if info.confluence_space:
                file_env["CONFLUENCE_SPACE_KEY"] = info.confluence_space
            results.append(self._upload_one(p, parent_page_id, file_env, progress_callback))
        return results

    def _upload_one(
        self,
        path: Path,
        parent_page_id: str | None,
        env: dict,
        callback: Callable | None,
    ) -> tuple[Path, bool, str]:
        if callback:
            callback(str(path), f"Uploading {path.name}...")

        cmd = self._build_cmd(path, parent_page_id)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if callback:
                callback(str(path), f"x {msg}")
            return path, False, msg

        if callback:
            if result.stdout.strip():
                callback(str(path), f"[stdout]\n{result.stdout.strip()}")
            if result.stderr.strip():
                callback(str(path), f"[stderr]\n{result.stderr.strip()}")

        page_info = self._parse_page_info(result.stdout + "\n" + result.stderr)
        if page_info:
            try:
                page_id = page_info["confluence_id"]
                try:
                    details = self.config.fetch_page_details(page_id)
                    page_info.update({
                        "confluence_page_name": details["confluence_page_name"],
                        "confluence_url": details["confluence_url"],
                        "confluence_space": details["confluence_space"],
                    })
                except Exception as api_err:
                    if callback:
                        callback(str(path), f"⚠ Failed to fetch page details from API: {api_err}. Saving basic ID info.")
                self.tracker.write_sync_state(path, page_info)
            except Exception as e:
                if callback:
                    callback(str(path), f"⚠ Uploaded but failed to save sync state: {e}")
        else:
            if callback:
                callback(str(path), "⚠ Warning: Could not find Page ID in command output. Local sync state was not updated.")

        if callback:
            callback(str(path), f"Uploaded {path.name}")
        return path, True, result.stdout

    def _build_cmd(self, path: Path, parent_page_id: str | None = None) -> list[str]:
        exe = shutil.which("md2conf")
        base = [exe] if exe else [sys.executable, "-m", "md2conf"]
        cmd = base + [str(path)]
        if parent_page_id:
            cmd += ["--root-page", parent_page_id]
        if self.config.skip_title_heading:
            cmd.append("--skip-title-heading")
        if self.config.mermaid_mode == "local":
            cmd.append("--render-mermaid")
        elif self.config.mermaid_mode == "macro":
            cmd.append("--no-render-mermaid")
        
        if self.config.plantuml_mode == "macro":
            cmd.append("--no-render-plantuml")

        cmd.append("--no-force-valid-url")
        cmd.append("--no-generated-by")
        return cmd

    def _parse_page_info(self, output: str) -> dict | None:
        # md2conf prints "Page ID: <id>" on success or logs page updates/checksums in stderr.
        import re
        patterns = [
            r"Page\s+ID:\s*(\d+)",
            r"Up-to-date\s+page\s*\(matching\s+checksum\):\s*(\d+)",
            r"Up-to-date\s+page\s*\(unchanged\s+content\):\s*(\d+)",
            r"Detected\s+page\s+with\s+updated\s+content:\s*(\d+)",
            r"Detected\s+page\s+with\s+new\s+title:\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                page_id = match.group(1)
                return {
                    "confluence_id": page_id,
                    "confluence_space": self.config.default_space,
                }
        return None
