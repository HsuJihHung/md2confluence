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


def test_write_sync_state_preserves_body(tmp_path):
    path = tmp_path / "a.md"
    body = "# My Document\n\nSome content here."
    path.write_text(body, encoding="utf-8")
    tracker = FileTracker()
    tracker.write_sync_state(path, {"confluence_id": "789", "confluence_space": "TEAM"})
    # Body must survive the frontmatter write
    post = __import__("frontmatter").load(str(path))
    assert "# My Document" in post.content
    assert "Some content here" in post.content


def test_write_sync_state_merges_existing_frontmatter(tmp_path):
    path = tmp_path / "a.md"
    _write_md(path, "# Hello", {"confluence_id": "123", "confluence_space": "OLD"})
    tracker = FileTracker()
    tracker.write_sync_state(path, {"confluence_id": "123", "confluence_space": "NEW"})
    fm = tracker.read_frontmatter(path)
    assert fm["confluence_space"] == "NEW"
    assert fm["confluence_id"] == "123"


def test_write_sync_state_is_idempotent(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Hello", encoding="utf-8")
    tracker = FileTracker()
    tracker.write_sync_state(path, {"confluence_id": "111"})
    results = tracker.scan(tmp_path)
    assert results[0].status == SyncStatus.SYNCED


def test_scan_empty_file(tmp_path):
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    results = FileTracker().scan(tmp_path)
    assert results[0].status == SyncStatus.NOT_LINKED


def test_read_frontmatter_malformed_yaml(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("---\n: invalid: yaml: :\n---\n# Body", encoding="utf-8")
    fm = FileTracker().read_frontmatter(path)
    assert isinstance(fm, dict)  # never raises, returns {} or partial
