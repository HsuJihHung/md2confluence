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
