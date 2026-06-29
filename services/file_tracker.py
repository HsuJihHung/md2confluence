import hashlib
import os
import re
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
    FAILED = "failed"  # set by UploadService/DownloadService on error, not by scan()


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
            # File has no parseable frontmatter — start fresh with empty metadata
            post = fm_lib.Post(self._strip_frontmatter_manually(path.read_text(encoding="utf-8")))

        _PAGE_ID_REGEXP = re.compile(r"<!--\s+confluence[-_]page[-_]id:\s*(\d+)\s+-->")
        _SPACE_KEY_REGEXP = re.compile(r"<!--\s+confluence[-_]space[-_]key:\s*(\S+)\s+-->")

        cid = page_info.get("confluence_id")
        space = page_info.get("confluence_space")

        content = post.content
        if cid:
            if _PAGE_ID_REGEXP.search(content):
                content = _PAGE_ID_REGEXP.sub(f"<!-- confluence-page-id: {cid} -->", content)
            else:
                content = f"<!-- confluence-page-id: {cid} -->\n" + content

        if space:
            if _SPACE_KEY_REGEXP.search(content):
                content = _SPACE_KEY_REGEXP.sub(f"<!-- confluence-space-key: {space} -->", content)
            else:
                content = f"<!-- confluence-space-key: {space} -->\n" + content

        post.content = content

        post.metadata.update({
            **page_info,
            "confluence_last_sync": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confluence_content_hash": f"sha256:{self.compute_body_hash_from_text(post.content)}",
        })
        # Atomic write: write to temp then rename
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(fm_lib.dumps(post), encoding="utf-8")
        os.replace(tmp, path)

    def compute_body_hash(self, path: Path) -> str:
        try:
            body = fm_lib.load(str(path)).content
        except Exception:
            # If frontmatter parsing fails, treat the whole file as body
            # (no frontmatter to strip) rather than risking a corrupt hash
            body = self._strip_frontmatter_manually(path.read_text(encoding="utf-8"))
        return self.compute_body_hash_from_text(body)

    def _strip_frontmatter_manually(self, text: str) -> str:
        """Strip leading frontmatter block (--- ... ---) if present, else return as-is."""
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return text
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "".join(lines[i + 1:])
        return text  # no closing --- found, treat whole file as body

    def compute_body_hash_from_text(self, body: str) -> str:
        return hashlib.sha256(body.encode("utf-8")).hexdigest()
