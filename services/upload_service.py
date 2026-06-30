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
        custom_titles: dict[Path, str] | None = None,
    ) -> list[tuple[Path, bool, str]]:
        results = []
        custom_titles = custom_titles or {}
        for p in paths:
            file_env = {**os.environ, **self.config.as_env_dict()}
            info = self.tracker._inspect(p)
            space_key = None
            if info.confluence_space:
                space_key = info.confluence_space

            if not space_key and parent_page_id:
                try:
                    space_key = self.config.fetch_space_key_for_page(parent_page_id)
                except Exception as e:
                    if progress_callback:
                        progress_callback(str(p), f"⚠ Failed to fetch space key for parent page '{parent_page_id}': {e}")

            if not space_key and info.confluence_id:
                try:
                    space_key = self.config.fetch_space_key_for_page(info.confluence_id)
                except Exception as e:
                    if progress_callback:
                        progress_callback(str(p), f"⚠ Failed to fetch space key for existing page '{info.confluence_id}': {e}")

            if space_key:
                file_env["CONFLUENCE_SPACE_KEY"] = space_key

            custom_title = custom_titles.get(p)
            if custom_title:
                # Write the temporary title to frontmatter of the uploaded copy or directly write to state
                # Wait, md2conf reads the frontmatter 'title' or the first H1 header in the file.
                # Let's inspect the original file's frontmatter.
                # We can temporarily update the confluence_page_name in frontmatter of the file before uploading,
                # or create a temporary file with the updated frontmatter title.
                # Let's see if md2conf uses "title" frontmatter. Yes, it says "does not apply if title comes from front-matter".
                # Let's write the custom title directly to the file's frontmatter before executing, and restore it if needed,
                # or write a temporary copy. Let's write a temporary copy or just write to the file's frontmatter,
                # which is actually a sync state property. Let's see if we can write "title" in frontmatter.
                # If we modify the original file's frontmatter to include "title: Custom Title", md2conf will pick it up.
                # Let's write the custom title to the frontmatter using tracker.write_sync_state or read/write frontmatter directly.
                pass
            results.append(self._upload_one(p, parent_page_id, file_env, progress_callback, custom_title=custom_title))
        return results

    def _upload_one(
        self,
        path: Path,
        parent_page_id: str | None,
        env: dict,
        callback: Callable | None,
        custom_title: str | None = None,
    ) -> tuple[Path, bool, str]:
        if callback:
            callback(str(path), f"Uploading {path.name}...")

        # If a custom title is provided, temporarily write it to the frontmatter of the file
        original_content = None
        if custom_title:
            try:
                original_content = path.read_text(encoding="utf-8")
                # Import frontmatter to manipulate
                import frontmatter as fm_lib
                try:
                    post = fm_lib.load(str(path))
                except Exception:
                    post = fm_lib.Post(self.tracker._strip_frontmatter_manually(original_content))
                post.metadata["title"] = custom_title
                post.metadata["confluence_page_name"] = custom_title
                path.write_text(fm_lib.dumps(post), encoding="utf-8")
            except Exception as e:
                if callback:
                    callback(str(path), f"⚠ Failed to set temporary custom title: {e}")

        try:
            cmd = self._build_cmd(path, parent_page_id)
            run_env = env.copy()
            run_env["PYTHONIOENCODING"] = "utf-8"
            run_env["PYTHONUTF8"] = "1"
            raw_result = subprocess.run(cmd, env=run_env, capture_output=True)
            
            def decode_bytes(b) -> str:
                if isinstance(b, str):
                    return b
                if not b:
                    return ""
                for enc in ["utf-8", "gbk", "gb18030", "cp950", "utf-16", "latin-1"]:
                    try:
                        return b.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return b.decode("utf-8", errors="replace")

            stdout = decode_bytes(raw_result.stdout)
            stderr = decode_bytes(raw_result.stderr)
            
            class DecodedResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr
            result = DecodedResult(raw_result.returncode, stdout, stderr)
        finally:
            # Always restore the original content if we modified it
            if original_content is not None:
                try:
                    path.write_text(original_content, encoding="utf-8")
                except Exception as e:
                    if callback:
                        callback(str(path), f"⚠ Failed to restore original file content: {e}")

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
        cmd += ["--loglevel", "info"]
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
