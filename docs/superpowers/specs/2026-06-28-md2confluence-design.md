# md2confluence — Design Spec

**Date:** 2026-06-28  
**Status:** Approved

---

## 1. Overview

A standalone desktop-style application for bidirectional sync between local Markdown files and Confluence pages. The app runs as a local web server and opens in the user's default browser — no installation required beyond a single executable.

**Core use cases:**
- Upload one or more local `.md` files to Confluence (create or update pages)
- Download a Confluence page (or a full page hierarchy) to local Markdown files
- Track which local files are linked to which Confluence pages, using frontmatter

**Target user:** Individual developer or technical writer syncing documentation between a local directory and Confluence. Supports both Confluence Cloud and Confluence Server/Data Center.

---

## 2. Distribution

| Attribute | Decision |
|---|---|
| UI | NiceGUI — local web server, opens in browser |
| Bundle | PyInstaller `.exe` (Windows), single portable executable |
| Python required | No — bundled by PyInstaller |
| Config stored | `~/.md2confluence/settings.json` |

The app launches a NiceGUI server on a random available port and opens `http://localhost:<port>` in the default browser automatically.

---

## 3. Architecture

Three layers with strict separation:

```
┌─────────────────────────────────────────┐
│           UI Layer (NiceGUI)            │
│  app.py · file_panel · detail_panel     │
│  download_dialog · config_page          │
├─────────────────────────────────────────┤
│         Service Layer (Python)          │
│  UploadService · DownloadService        │
│  FileTracker · ConfluenceConfig         │
├─────────────────────────────────────────┤
│          Package Layer (PyPI)           │
│  markdown-to-confluence                 │
│  confluence-markdown-exporter           │
└─────────────────────────────────────────┘
         Storage
         ~/.md2confluence/settings.json   ← credentials, preferences
         <each .md file frontmatter>      ← Confluence link + sync state
```

**Rule:** The UI layer never calls the Confluence API or reads/writes frontmatter directly. All such operations go through the service layer.

**Background tasks:** Uploads and downloads run in NiceGUI background tasks (asyncio) so the UI stays responsive. Progress is reported via callbacks that update UI components.

---

## 4. File Tracking — Frontmatter

Each `.md` file that has been linked to a Confluence page carries these frontmatter fields:

```yaml
---
confluence_id: "98321"
confluence_space: "TEAM"
confluence_page_name: "Project README"
confluence_url: "https://company.atlassian.net/wiki/spaces/TEAM/pages/98321"
confluence_last_sync: "2026-06-28T08:14:04"
confluence_content_hash: "sha256:a3f2..."
---
```

`confluence_content_hash` is a SHA-256 of the file body content (everything after the closing `---` of the frontmatter block) at last sync time. On Refresh, the app recomputes the hash of the body and compares — if it differs, the file is marked "modified locally." Hashing the body only avoids a circular dependency where writing the hash itself changes the hash.

**Status values:**

| Status | Meaning |
|---|---|
| synced | File is linked; content hash matches last sync |
| modified locally | File is linked; content has changed since last sync |
| not linked | No `confluence_id` in frontmatter |
| failed | Last upload/download operation returned an error |

---

## 5. UI Layout

### 5.1 Main View — File List + Detail Panel

```
┌─────────────────────────────────────────────────────────┐
│ md2confluence  [📁 dir path]  [Browse] [⟳ Refresh]      │
│                               [⬇ Download Page…] [⚙ Config] │
├──────────────────┬──────────────────────────────────────┤
│ View: [≡ Flat]   │                                      │
│       [⊞ Tree]   │  <filename>.md              [● status]│
│ ─────────────── │  <full path>                         │
│ ● README.md      │                                      │
│   ID:98321 2h ago│  ┌─ Confluence ───────────────────┐ │
│ ○ design.md      │  │ Page name   Project README      │ │
│   modified       │  │ Path        TEAM › Eng › ...    │ │
│ ─ api-docs.md    │  │ Page ID     98321               │ │
│   not linked     │  │ Space       TEAM                │ │
│ ● onboarding.md  │  │ Last sync   2026-06-28 08:14    │ │
│ ✕ architecture.md│  │ Open        View in Confluence ↗│ │
│ ─ changelog.md   │  └────────────────────────────────┘ │
│                  │                                      │
│                  │  [⬆ Upload]  [⬇ Pull]  [🔗 Change ID]│
│                  │                                      │
│                  │  Last Operation Log                  │
│                  │  [08:14:02] Uploading README.md...  │
│                  │  [08:14:04] ✓ Page updated: 98321   │
├──────────────────┴──────────────────────────────────────┤
│ ● Connected  company.atlassian.net    3 synced · 1 modified · 2 unlinked · 1 error │
└─────────────────────────────────────────────────────────┘
```

**Left panel — file list:**
- Toggle between flat list and directory tree view (persisted in settings)
- Each row shows filename, status dot, Confluence ID + last sync time (or "not linked" / "last upload failed")
- Color coding: green (synced), orange (modified locally), grey (not linked), red (failed)

**Right panel — detail:**
- File path
- Confluence info card: page name, breadcrumb path, page ID, space, last sync timestamp, link to open in Confluence
- Three action buttons: Upload to Confluence / Pull from Confluence / Change ID…
- Per-file operation log (last upload or download)

**Toolbar:**
- Directory path box + Browse button
- Refresh button — rescans directory, re-reads frontmatter, recomputes content hashes. **No API calls.**
- "⬇ Download Page…" button — opens Download dialog
- Config button — opens Config page

**Status bar:**
- Connection indicator (green dot = connected, red = not connected)
- Active Confluence server hostname
- File counts: synced / modified (locally changed since last sync) / unlinked / error

### 5.2 Download Page Dialog

Opened from the toolbar "⬇ Download Page…" button.

Fields:
- **URL or Page ID** — accepts full Confluence URL or bare page ID; resolves page title live
- **Scope** — Single page / Page + all children (recursive)
- **Save to** — target directory (defaults to currently open directory)
- **Options:**
  - Download attachments and images (default: on)
  - Write Confluence ID to frontmatter (default: on)
  - Overwrite existing files (default: off) — when off, files that already exist locally are skipped; when on, existing files are replaced with the Confluence version

When scope is "recursive", the page hierarchy is mirrored as subdirectories.

### 5.3 Config Page

Four sections, opened from the toolbar Config button:

**Confluence Connection**
- Deployment toggle: Cloud / Server & Data Center
- Cloud fields: domain, email, API token, default space key
- Server fields: server URL, context path (optional), auth method (username+password or PAT), default space key
- "Test Connection" button with live result

**Diagram Rendering**
- Mermaid: render locally via `mmdc` CLI, or embed as Confluence macro
- PlantUML: remote server (URL configurable, defaults to public plantuml.com) or local jar

**Upload Defaults**
- Default parent page ID (optional)
- Skip title heading (default: on)
- Auto-upload local images as attachments (default: on)

**App Preferences**
- Theme: dark / light (persisted)
- Default file view: flat / tree (persisted)
- Last directory (auto-remembered)

---

## 6. Service Layer

### UploadService
- Accepts a list of file paths and a `ConfluenceConfig`
- Calls `markdown-to-confluence` Python API to convert and upload each file
- Reports progress via async callback: `(file, step, message)`
- On success: calls `FileTracker.write_sync_state()` to update frontmatter
- On failure: sets file status to "failed" with error message in log

### DownloadService
- Accepts a page URL or ID, scope (single/recursive), target directory, and options
- Calls `confluence-markdown-exporter` Python API
- For recursive downloads, mirrors Confluence hierarchy as subdirectories
- On success: calls `FileTracker.write_sync_state()` to write frontmatter to downloaded files

### FileTracker
- `scan(directory)` — walks directory tree, finds all `.md` files, reads frontmatter, computes content hashes, returns file list with status
- `read_frontmatter(path)` — returns parsed frontmatter dict
- `write_sync_state(path, page_info)` — writes/updates frontmatter fields after sync
- `compute_hash(path)` — SHA-256 of file content

### ConfluenceConfig
- Loads from `~/.md2confluence/settings.json`
- Exposes typed fields for Cloud vs Server credentials
- `test_connection()` — makes a lightweight API call (e.g., get current user) and returns success/error

---

## 7. Supported Content

| Element | Support | Notes |
|---|---|---|
| Tables | ✓ | Full GFM table support via `markdown-to-confluence` |
| Mermaid diagrams | ✓ | Local render (mmdc) or Confluence macro |
| PlantUML diagrams | ✓ | Remote server or local jar |
| Code blocks | ✓ | Syntax highlighting preserved |
| Images (local) | ✓ | Auto-uploaded as page attachments |
| Images (external URL) | ✓ | Embedded as-is |
| Attachments (download) | ✓ | Downloaded alongside .md files |
| Admonitions / callouts | ✓ | GitHub-style alert boxes → Confluence panels |
| Collapsed sections | ✓ | `<details>` → Confluence expand macro |
| Internal links | ✓ | Resolved to Confluence page URLs within synced hierarchy |

---

## 8. Project Structure

```
md2confluence/
├── app.py                    # Entry point — starts NiceGUI
├── ui/
│   ├── main_layout.py        # Split panel shell
│   ├── file_panel.py         # Left: file list (flat + tree)
│   ├── detail_panel.py       # Right: file detail + actions
│   ├── download_dialog.py    # Download page dialog
│   └── config_page.py        # Configuration page
├── services/
│   ├── upload_service.py
│   ├── download_service.py
│   ├── file_tracker.py
│   └── confluence_config.py
├── build/
│   └── md2confluence.spec    # PyInstaller spec
├── requirements.txt
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-28-md2confluence-design.md
```

---

## 9. Key Decisions Log

| Decision | Choice | Reason |
|---|---|---|
| Distribution | Local web UI (NiceGUI) | Richest UI options, cross-OS, no native widget quirks |
| Layout | File list + detail panel | Maps to "pick file → see link → act" workflow |
| Architecture | Service layer pattern | Clean separation; package API changes isolated to services |
| File tracking | Frontmatter | Durable, travels with files, works with existing packages |
| Confluence versions | Both Cloud + Server/DC | Cloud for testing, Server for company use |
| "Re-download" naming | Renamed to "Pull from Confluence" | Direction is explicit — always overwrites local file |
| Sync definition | Hash-based, local only | Can't detect server-side edits without API call; Refresh is cheap |
| Overwrite on download | Off by default | Protects local edits; user opts in explicitly |
