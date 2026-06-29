import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from services.confluence_config import ConfluenceConfig, DeploymentType
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

        # Create temporary config file to provide credentials to cme without interactive prompts
        auth_confluence = {}
        urls_to_register = []

        parsed_page = urlparse(page_url)
        if parsed_page.scheme and parsed_page.netloc:
            base = f"{parsed_page.scheme}://{parsed_page.netloc}"
            urls_to_register.append(base)
            path_parts = [p for p in parsed_page.path.split("/") if p]
            if path_parts and path_parts[0] not in ("display", "spaces", "pages"):
                urls_to_register.append(f"{base}/{path_parts[0]}")

        if self.config.deployment == DeploymentType.CLOUD:
            domain = self.config.cloud_domain
            if domain:
                if not domain.startswith(("http://", "https://")):
                    if "." not in domain:
                        domain = f"{domain}.atlassian.net"
                    domain = f"https://{domain}"
                urls_to_register.append(domain)
            
            api_details = {
                "username": self.config.cloud_email,
                "api_token": self.config.cloud_api_token,
                "pat": "",
                "session_cookies": "",
                "cloud_id": ""
            }
        else:
            if self.config.server_url:
                urls_to_register.append(self.config.server_url)
            api_details = {
                "username": self.config.server_username,
                "api_token": self.config.server_password if not self.config.server_pat else "",
                "pat": self.config.server_pat,
                "session_cookies": "",
                "cloud_id": ""
            }

        for u in urls_to_register:
            if u:
                auth_confluence[u.rstrip("/")] = api_details

        temp_config = {
            "auth": {
                "confluence": auth_confluence
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(temp_config, tf, indent=2)
            temp_config_path = tf.name

        try:
            env = {**os.environ}
            env["PYTHONIOENCODING"] = "utf-8"
            env["CME_CONFIG_PATH"] = temp_config_path
            env["CME_EXPORT__OUTPUT_PATH"] = str(target_dir)
            env["CME_EXPORT__SKIP_UNCHANGED"] = "true"
            env["CME_EXPORT__ATTACHMENTS_EXPORT"] = "referenced" if download_attachments else "disabled"

            # If overwrite is True, remove existing lockfile to force cme to re-export everything
            # and generate a fresh lockfile.
            if overwrite:
                for p in [target_dir / "confluence-lock.json", target_dir.parent / "confluence-lock.json", Path.cwd() / "confluence-lock.json"]:
                    try:
                        if p.exists():
                            p.unlink()
                    except Exception:
                        pass

            # Record existing files and their modification times
            existing_files_mtime = {}
            for path in target_dir.rglob("*.md"):
                try:
                    existing_files_mtime[path] = path.stat().st_mtime
                except Exception:
                    pass

            cmd = self._build_cmd(page_url, scope)
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")

            if result.returncode != 0:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                if progress_callback:
                    progress_callback(f"x {msg}")
                return False, msg

            if write_frontmatter:
                # Find which files were actually added or modified
                new_or_modified = []
                for path in target_dir.rglob("*.md"):
                    try:
                        mtime = path.stat().st_mtime
                        if path not in existing_files_mtime or mtime != existing_files_mtime[path]:
                            new_or_modified.append(path)
                    except Exception:
                        pass
                self._write_frontmatter_for_new_files(new_or_modified, target_dir, page_url)

            if progress_callback:
                progress_callback("✓ Download complete")
            return True, result.stdout
        finally:
            try:
                os.unlink(temp_config_path)
            except Exception:
                pass

    def _build_cmd(self, url: str, scope: DownloadScope) -> list[str]:
        exe = shutil.which("cme")
        base = [exe] if exe else [sys.executable, "-m", "cme"]
        subcommand = "pages" if scope == DownloadScope.SINGLE else "pages-with-descendants"
        return base + [subcommand, url]

    def _write_frontmatter_for_new_files(self, paths: list[Path], target_dir: Path, source_url: str) -> None:
        # Load confluence-lock.json if it exists to get page metadata (confluence_id, etc.)
        lock_data = {}
        lockfile_path = None
        for p in [target_dir / "confluence-lock.json", target_dir.parent / "confluence-lock.json", Path.cwd() / "confluence-lock.json"]:
            if p.exists():
                lockfile_path = p
                break

        path_to_metadata = {}
        if lockfile_path:
            try:
                with open(lockfile_path, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                
                orgs = lock_data.get("orgs", {})
                for org_url, org_val in orgs.items():
                    spaces = org_val.get("spaces", {})
                    for space_key, space_val in spaces.items():
                        pages = space_val.get("pages", {})
                        for page_id, page_val in pages.items():
                            export_path = page_val.get("export_path")
                            if export_path:
                                abs_path = (lockfile_path.parent / Path(export_path)).resolve()
                                path_to_metadata[abs_path] = {
                                    "confluence_id": str(page_id),
                                    "confluence_space": str(space_key),
                                    "confluence_page_name": str(page_val.get("title", "")),
                                    "confluence_url": f"{org_url.rstrip('/')}/spaces/{space_key}/pages/{page_id}",
                                }
            except Exception as exc:
                _log.warning("Failed to parse confluence-lock.json: %s", exc)

        for path in paths:
            resolved_path = path.resolve()
            metadata = path_to_metadata.get(resolved_path)
            
            fm = self.tracker.read_frontmatter(path)
            if metadata:
                try:
                    self.tracker.write_sync_state(path, metadata)
                except Exception as exc:
                    _log.warning("Failed to write frontmatter metadata for %s: %s", path, exc)
            elif not fm.get("confluence_id"):
                try:
                    self.tracker.write_sync_state(path, {"confluence_url": source_url})
                except Exception as exc:
                    _log.warning("Failed to write frontmatter for %s: %s", path, exc)
